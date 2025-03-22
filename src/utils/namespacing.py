"""Utility for managing namespaced cache keys."""

from typing import Dict, Any

class NamespaceManager:
    """Manages namespacing for cache keys to prevent collisions.
    
    Provides consistent methods for adding and removing namespace prefixes from keys.
    """
    
    def __init__(self, namespace: str = "default"):
        """Initialize the namespace manager.
        
        Args:
            namespace: The namespace to use for keys
        """
        self.namespace = namespace
    
    def namespace_key(self, key: str) -> str:
        """Add namespace prefix to a key.
        
        Args:
            key: The original key
            
        Returns:
            str: The namespaced key
        """
        if self.namespace == "default":
            return key
        return f"{self.namespace}:{key}"
    
    def remove_namespace(self, namespaced_key: str) -> str:
        """Remove namespace prefix from a key.
        
        Args:
            namespaced_key: The namespaced key
            
        Returns:
            str: The original key without namespace
        """
        if self.namespace == "default" or ":" not in namespaced_key:
            return namespaced_key
        _, key = namespaced_key.split(":", 1)
        return key
    
    def namespace_keys_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add namespace prefix to all keys in a dictionary.
        
        Args:
            data: Dictionary with original keys
            
        Returns:
            Dict[str, Any]: Dictionary with namespaced keys
        """
        return {self.namespace_key(key): value for key, value in data.items()}
    
    def remove_namespace_from_keys_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove namespace prefix from all keys in a dictionary.
        
        Args:
            data: Dictionary with namespaced keys
            
        Returns:
            Dict[str, Any]: Dictionary with original keys
        """
        return {self.remove_namespace(key): value for key, value in data.items()} 