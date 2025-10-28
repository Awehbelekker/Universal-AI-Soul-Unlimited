"""
Dependency Injection Container
==============================

Container for managing dependencies across the Universal Soul AI system.
"""

import inspect
from typing import Dict, Any, Type, TypeVar, Callable, Optional
from core.interfaces.base_interfaces import IContainer
from core.interfaces.exceptions import (
    ContainerError, ServiceNotFoundError, CircularDependencyError
)

T = TypeVar('T')


class Container(IContainer):
    """Dependency injection container implementation"""
    
    def __init__(self):
        self._services: Dict[Type, Type] = {}
        self._instances: Dict[Type, Any] = {}
        self._singletons: Dict[Type, bool] = {}
        self._factories: Dict[Type, Callable] = {}
        self._resolving: set = set()
    
    def register(self, interface: Type[T], implementation: Type[T], 
                singleton: bool = True) -> None:
        """Register an implementation for an interface"""
        if not issubclass(implementation, interface):
            raise ContainerError(
                f"{implementation} does not implement {interface}",
                "INVALID_IMPLEMENTATION"
            )
        
        self._services[interface] = implementation
        self._singletons[interface] = singleton
    
    def register_instance(self, interface: Type[T], instance: T) -> None:
        """Register a specific instance"""
        if not isinstance(instance, interface):
            raise ContainerError(
                f"Instance does not implement {interface}",
                "INVALID_INSTANCE"
            )
        
        self._instances[interface] = instance
        self._singletons[interface] = True
    
    def register_factory(self, interface: Type[T], 
                        factory: Callable[[], T]) -> None:
        """Register a factory function"""
        self._factories[interface] = factory
    
    def get(self, interface: Type[T]) -> T:
        """Get implementation for interface"""
        # Check for existing instance
        if interface in self._instances:
            return self._instances[interface]
        
        # Check for factory
        if interface in self._factories:
            instance = self._factories[interface]()
            if self._singletons.get(interface, True):
                self._instances[interface] = instance
            return instance
        
        # Check for registered service
        if interface not in self._services:
            raise ServiceNotFoundError(
                f"No registration found for {interface}",
                "SERVICE_NOT_FOUND"
            )
        
        # Check for circular dependency
        if interface in self._resolving:
            raise CircularDependencyError(
                f"Circular dependency detected for {interface}",
                "CIRCULAR_DEPENDENCY"
            )
        
        try:
            self._resolving.add(interface)
            implementation = self._services[interface]
            instance = self.resolve(implementation)
            
            # Store as singleton if configured
            if self._singletons.get(interface, True):
                self._instances[interface] = instance
            
            return instance
        finally:
            self._resolving.discard(interface)
    
    def resolve(self, target_type: Type[T]) -> T:
        """Resolve all dependencies for target type"""
        # Get constructor signature
        signature = inspect.signature(target_type.__init__)
        
        # Build arguments
        kwargs = {}
        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            
            # Skip parameters with default values that aren't annotations
            if param.annotation == param.empty:
                if param.default != param.empty:
                    continue
                raise ContainerError(
                    f"Cannot resolve parameter '{param_name}' for {target_type}",
                    "UNRESOLVABLE_PARAMETER"
                )
            
            # Resolve dependency
            dependency = self.get(param.annotation)
            kwargs[param_name] = dependency
        
        # Create instance
        return target_type(**kwargs)
    
    def clear(self) -> None:
        """Clear all registrations"""
        self._services.clear()
        self._instances.clear()
        self._singletons.clear()
        self._factories.clear()
        self._resolving.clear()
    
    def is_registered(self, interface: Type) -> bool:
        """Check if interface is registered"""
        return (interface in self._services or 
                interface in self._instances or 
                interface in self._factories)
    
    def get_registrations(self) -> Dict[str, str]:
        """Get all registrations for debugging"""
        registrations = {}
        
        for interface, implementation in self._services.items():
            registrations[interface.__name__] = implementation.__name__
        
        for interface, instance in self._instances.items():
            registrations[interface.__name__] = f"Instance: {type(instance).__name__}"
        
        for interface, factory in self._factories.items():
            registrations[interface.__name__] = f"Factory: {factory.__name__}"
        
        return registrations


# Global container instance
_container: Optional[Container] = None


def get_container() -> Container:
    """Get the global container instance"""
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Reset the global container"""
    global _container
    _container = None


def register_service(interface: Type[T], implementation: Type[T], 
                    singleton: bool = True) -> None:
    """Register a service in the global container"""
    container = get_container()
    container.register(interface, implementation, singleton)


def register_instance(interface: Type[T], instance: T) -> None:
    """Register an instance in the global container"""
    container = get_container()
    container.register_instance(interface, instance)


def register_factory(interface: Type[T], factory: Callable[[], T]) -> None:
    """Register a factory in the global container"""
    container = get_container()
    container.register_factory(interface, factory)


def get_service(interface: Type[T]) -> T:
    """Get a service from the global container"""
    container = get_container()
    return container.get(interface)


def is_service_registered(interface: Type) -> bool:
    """Check if service is registered in global container"""
    container = get_container()
    return container.is_registered(interface)