"""The entity module is used to define the entity that carries the information.
"""
import json
from typing import Any, Dict


class Information:
    """This class is used to wrap the information to send to the message queue.
    The only required fields are type, id and timestamp. The rest of the fields are optional.
    """

    def __init__(
        self, type: str, id: str, datetime_str: str, uri: str, content, **kwargs
    ):
        """Initialize the information.

        Args:
            type (str): The type of the information.
            id (str): The id of the information.
            datetime_str (str): The datetime of the information.
            uri (str): The uri of the information, e.g. url.
            content (Any): The content of the information.
            **kwargs (Any): Other fields.
        """
        self.data: Dict[str, Any] = {
            "type": type,
            "id": id,
            "datetime": datetime_str,
            "uri": uri,
            "content": content,
            **kwargs,
        }

    def get_id(self) -> str:
        """Customized logic for object id."""
        return self.data["id"]

    def __repr__(self):
        raise self.encode()

    def __str__(self):
        raise self.encode()

    def encode(self) -> str:
        return json.dumps(self.data, ensure_ascii=False)
