from functools import lru_cache, reduce
from typing import Dict, List, Tuple, Optional

INDENT = " " * 4
LINE_BREAK = "\r\n"


@lru_cache
def camel_to_joined_lower(message_class_name: str) -> str:
    return reduce(lambda c, e: c + ((("_" if e[0] != e[1] else "") + e[1]) if c else e[1]),
                  zip(message_class_name, message_class_name.lower()), "")


def produce_imports_block(has_cache: bool, has_random_selector: bool) -> str:
    out = "from dataclasses import dataclass" + LINE_BREAK
    if has_random_selector:
        out += "from random import sample" + LINE_BREAK
    out += LINE_BREAK + "from ipv8.community import Community" + LINE_BREAK
    if has_cache:
        out += ("from ipv8.lazy_community import lazy_wrapper, retrieve_cache" + LINE_BREAK
                + "from ipv8.messaging.payload_dataclass import overwrite_dataclass" + LINE_BREAK)
    else:
        out += ("from ipv8.lazy_community import lazy_wrapper" + LINE_BREAK
                + "from ipv8.messaging.payload_dataclass import overwrite_dataclass, type_from_format" + LINE_BREAK
                + "from ipv8.requestcache import RandomNumberCache, RequestCache" + LINE_BREAK)
    out += LINE_BREAK + "dataclass = overwrite_dataclass(dataclass)" + LINE_BREAK
    if has_cache:
        out += "Identifier = type_from_format(\"I\")" + LINE_BREAK
    return out


def produce_message_block(message_number: int, message_class_name: str, fields: Dict[str, str], has_cache=False) -> str:
    return (f"@dataclass(msg_id={message_number})" + LINE_BREAK
            + f"class {message_class_name}:" + LINE_BREAK
            + INDENT + (LINE_BREAK + INDENT).join(f"{k}: {v}" for k, v in fields.items()) + LINE_BREAK
            + ((INDENT + "identifier: Identifier" + LINE_BREAK) if has_cache else ""))


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
            + INDENT + f"community_id = {community_hash}")


def produce_init_block(message_classes: List[str], tasks: List[Tuple[int, float]], has_caches=False) -> str:
    out = (INDENT + "def __init__(self, my_peer, endpoint, network):" + LINE_BREAK
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


def produce_message_producer_block(message_classes: List[str]) -> str:
    return (f"{INDENT}def produce_initial_message(peer: Peer, message_class: "
            f"Union[{', '.join(message_classes)}] -> Optional[Payload]:{LINE_BREAK}"
            f"{INDENT * 2}raise NotImplementedError(\"Fill this function with your message producing logic\")"
            f"{LINE_BREAK}")


def produce_selector_block(selector_id: int, linked_message_classes: List[str], all_peers: bool = False) -> str:
    out = f"{INDENT}def selector_{selector_id}(self):" + LINE_BREAK
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
                f")){LINE_BREAK}")
    return out


class Exporter:
    """
    TODO: Implement exporter_idea.txt template.
    """
    pass
