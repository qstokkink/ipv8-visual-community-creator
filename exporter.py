from functools import lru_cache, reduce
from typing import Dict, List, Tuple, Optional

from nodes import AllPeersNode, RandomPeerNode, CacheNode, MessageNode, PeriodicTaskNode

INDENT = " " * 4
LINE_BREAK = "\n"


@lru_cache
def camel_to_joined_lower(message_class_name: str) -> str:
    return reduce(lambda c, e: c + ((("_" if e[0] != e[1] else "") + e[1]) if c else e[1]),
                  zip(message_class_name, message_class_name.lower()), "")


def produce_imports_block(has_cache: bool, has_random_selector: bool) -> str:
    out = "from dataclasses import dataclass" + LINE_BREAK
    if has_random_selector:
        out += "from random import sample" + LINE_BREAK
    out += "from typing import Optional" + LINE_BREAK
    out += LINE_BREAK + "from ipv8.community import Community" + LINE_BREAK
    if has_cache:
        out += ("from ipv8.lazy_community import lazy_wrapper" + LINE_BREAK
                + "from ipv8.messaging.payload_dataclass import overwrite_dataclass, type_from_format" + LINE_BREAK
                + "from ipv8.requestcache import RandomNumberCache, RequestCache" + LINE_BREAK)
    else:
        out += ("from ipv8.lazy_community import lazy_wrapper, retrieve_cache" + LINE_BREAK
                + "from ipv8.messaging.payload_dataclass import overwrite_dataclass" + LINE_BREAK)
    out += "from ipv8.types import AnyPayload, AnyPayloadType, Endpoint, Network, Peer" + LINE_BREAK
    out += LINE_BREAK + "dataclass = overwrite_dataclass(dataclass)" + LINE_BREAK
    if has_cache:
        out += "Identifier = type_from_format(\"I\")" + LINE_BREAK
    return out


def produce_message_block(message_number: int, message_class_name: str, fields: Dict[str, str], has_cache=False) -> str:
    out = (f"@dataclass(msg_id={message_number})" + LINE_BREAK
           + f"class {message_class_name}:" + LINE_BREAK)
    if len(fields) == 0:
        out += INDENT + "pass" + LINE_BREAK
    else:
        out += INDENT + (LINE_BREAK + INDENT).join(f"{k}: {v}" for k, v in fields.items()) + LINE_BREAK
    if has_cache:
        out += INDENT + "identifier: Identifier" + LINE_BREAK
    return out


def produce_cache_block(cache_class_name: str, fields: Dict[str, str]) -> str:
    out = (f"class {cache_class_name}(RandomNumberCache)" + LINE_BREAK
           + INDENT + f"name = {cache_class_name}" + LINE_BREAK + LINE_BREAK
           + INDENT + "def __init__(self, request_cache: RequestCache, "
                    + ", ".join(f"{k}: {v}" for k, v in fields.items()) + ")" + LINE_BREAK
           + INDENT * 2 + f"super().__init__(request_cache, {cache_class_name}.name)" + LINE_BREAK
           + LINE_BREAK if len(fields) > 0 else "")
    for k, v in fields.items():
        out += INDENT * 2 + f"self.{k}: {v} = {k}" + LINE_BREAK
    return out


def produce_community_block(community_hash: str) -> str:
    return ("class MyCommunity(Community):" + LINE_BREAK
            + INDENT + f"community_id = b\"{community_hash}\"" + LINE_BREAK)


def produce_init_block(message_classes: List[str], tasks: List[Tuple[int, float]], has_caches=False) -> str:
    out = (INDENT + "def __init__(self, my_peer: Peer, endpoint: Endpoint, network: Network):" + LINE_BREAK
           + INDENT * 2 + "super().__init__(my_peer, endpoint, network)" + LINE_BREAK)
    out += LINE_BREAK if len(message_classes) > 0 else ""
    for message_class in message_classes:
        out += INDENT * 2 + (f"self.add_message_handler({message_class}, "
                             f"self.on_{camel_to_joined_lower(message_class)})" + LINE_BREAK)
    out += LINE_BREAK if len(tasks) > 0 else ""
    for task in tasks:
        task_id, task_interval = task
        out += INDENT * 2 + (f"self.register_anonymous_task(\"interval_task\", self.selector_{task_id}, "
                             f"interval={task_interval}, delay=0)" + LINE_BREAK)
    out += LINE_BREAK if has_caches else ""
    if has_caches:
        out += (INDENT * 2 + "self.request_cache = RequestCache()" + LINE_BREAK * 2
                + INDENT + "async def unload(self):" + LINE_BREAK
                + INDENT * 2 + "await self.request_cache.shutdown()" + LINE_BREAK
                + INDENT * 2 + "await super().unload()" + LINE_BREAK)
    return out


def produce_message_producer_block() -> str:
    return (f"{INDENT}def produce_initial_message(peer: Peer, message_class: AnyPayloadType) "
            f"-> Optional[AnyPayload]:{LINE_BREAK}"
            f"{INDENT * 2}raise NotImplementedError(\"Fill this function with your message producing logic\")"
            f"{LINE_BREAK}")


def produce_selector_block(selector_id: int, linked_message_classes: List[str],
                           all_peers: Optional[bool] = False) -> str:
    out = f"{INDENT}def selector_{selector_id}(self):" + LINE_BREAK
    if all_peers is None:
        out += INDENT * 2 + "pass" + LINE_BREAK
        return out
    peers_inst_name = "peer" if all_peers else "random_peer"
    if all_peers:
        out += INDENT * 2 + "for peer in self.get_peers():" + (LINE_BREAK if len(linked_message_classes) == 0 else "")
    else:
        out += (INDENT * 2 + "known_peers = self.get_peers()" + LINE_BREAK
                + INDENT * 2 + "if known_peers:" + LINE_BREAK
                + INDENT * 3 + f"{peers_inst_name} = sample(known_peers, 1)" + LINE_BREAK)
    for linked_message_class in linked_message_classes:
        out += LINE_BREAK
        out += INDENT * 3 + (f"message = self.produce_initial_message({peers_inst_name}, {linked_message_class})"
                             + LINE_BREAK)
        out += (INDENT * 3 + "if message is not None:" + LINE_BREAK
                + INDENT * 4 + f"self.ez_send({peers_inst_name}, message)" + LINE_BREAK)
    return out


def produce_message_handler_block(message_class_name: str, input_cache: Optional[str] = None,
                                  output_cache: Optional[str] = None, response: Optional[str] = None) -> str:
    out = f"{INDENT}@lazy_wrapper({message_class_name})" + LINE_BREAK
    if input_cache:
        out += f"{INDENT}@retrieve_cache({input_cache})" + LINE_BREAK
    out += (f"{INDENT}def on_{camel_to_joined_lower(message_class_name)}"
            f"(self, peer: Peer, message: {message_class_name}"
            + (f", cache: {input_cache}" if input_cache else "")
            + "):" + LINE_BREAK)
    out += INDENT * 2 + "raise NotImplementedError(\"Fill this function with your handling logic\")" + LINE_BREAK
    indents = 2
    if output_cache is not None:
        out += LINE_BREAK
        out += f"{INDENT * 2}cache = self.request_cache.add({output_cache}(self.request_cache, NotImplementedError("
        out += "\"Fill your cache fields here\""
        out += ")))" + LINE_BREAK
        if response is not None:
            out += INDENT * 2 + "if cache is not None:" + LINE_BREAK
            indents += 1
    if response is not None:
        out += LINE_BREAK if output_cache is None else ""
        out += (f"{INDENT * indents}self.ez_send(peer, {response}(NotImplementedError("
                "\"Fill your response message here\""
                f"))){LINE_BREAK}")
    return out


class Exporter:

    def __init__(self, nodes):
        super().__init__()

        self.all_peer_selector_nodes: List[AllPeersNode] = []
        self.random_peer_selector_nodes: List[RandomPeerNode] = []
        self.cache_nodes: List[CacheNode] = []
        self.message_nodes: List[MessageNode] = []
        self.task_nodes: List[PeriodicTaskNode] = []

        for node in nodes:
            if isinstance(node, AllPeersNode):
                self.all_peer_selector_nodes.append(node)
            elif isinstance(node, RandomPeerNode):
                self.random_peer_selector_nodes.append(node)
            elif isinstance(node, CacheNode):
                self.cache_nodes.append(node)
            elif isinstance(node, MessageNode):
                self.message_nodes.append(node)
            elif isinstance(node, PeriodicTaskNode):
                self.task_nodes.append(node)
            else:
                raise RuntimeError("Unknown node found!")

    def export(self, file_path):
        has_caches = len(self.cache_nodes) > 0
        has_random_selector = len(self.random_peer_selector_nodes) > 0

        code_import_block = produce_imports_block(has_caches, has_random_selector)
        code_message_blocks = []
        known_message_classes = []
        for i, message_node in enumerate(self.message_nodes):
            known_message_classes.append(message_node.display_title)
            code_message_blocks.append(produce_message_block(i, message_node.display_title,
                                                             message_node.custom_fields_dict, message_node.has_cache()))
        code_cache_blocks = []
        for cache_node in self.cache_nodes:
            code_cache_blocks.append(produce_cache_block(cache_node.display_title, cache_node.custom_fields_dict))
        code_community_block = produce_community_block("\\x00" * 20)  # TODO: base on defined messages
        code_init_block = produce_init_block(known_message_classes,
                                             [(i, node.interval) for i, node in enumerate(self.task_nodes)],
                                             has_caches)
        code_message_producer_block = produce_message_producer_block()
        code_message_selector_blocks = []
        for i, task_node in enumerate(self.task_nodes):
            selector_port = [port for port in task_node.outputs if port.label_str == "on_timer_fire"]
            if not selector_port:
                code_message_selector_blocks.append(produce_selector_block(i, [], None))
                continue
            selectors = selector_port[0].connections
            all_peers_links = []
            random_peers_links = []
            for selector_connection in selectors:
                selector = selector_connection.inp.node
                links_to = [port.connections for port in selector.outputs if port.label_str == "message"][0]
                links_to = [connection.inp.node.display_title for connection in links_to]
                if selector.title == "AllPeers":
                    all_peers_links.extend(links_to)
                else:
                    random_peers_links.extend(links_to)
            if all_peers_links:
                code_message_selector_blocks.append(produce_selector_block(i, all_peers_links, True))
            if random_peers_links:
                code_message_selector_blocks.append(produce_selector_block(i, random_peers_links, False))
        code_message_handler_blocks = []
        for message_node in self.message_nodes:
            input_caches = [port.connections for port in message_node.inputs if port.label_str == "retrieve_cache"][0]
            output_caches = [port.connections for port in message_node.outputs if port.label_str == "create_cache"][0]
            response_messages = [port.connections for port in message_node.outputs if port.label_str == "response"][0]
            input_cache = input_caches[0].inp.nodedisplay_title if input_caches else None
            output_cache = output_caches[0].inp.nodedisplay_title if output_caches else None
            response_message = response_messages[0].inp.node.display_title if response_messages else None
            code_message_handler_blocks.append(produce_message_handler_block(message_node.display_title, input_cache,
                                                                             output_cache, response_message))

        out = code_import_block + LINE_BREAK + LINE_BREAK
        out += LINE_BREAK.join(code_message_blocks) + LINE_BREAK
        out += LINE_BREAK.join(code_cache_blocks) + LINE_BREAK
        out += code_community_block + LINE_BREAK
        out += code_init_block + LINE_BREAK
        out += code_message_producer_block + LINE_BREAK  # TODO: This is a bit clunky, just call the Message constructor!
        out += LINE_BREAK.join(code_message_selector_blocks) + LINE_BREAK
        out += LINE_BREAK.join(code_message_handler_blocks)

        with open(file_path, "w") as fp:
            fp.write(out)
