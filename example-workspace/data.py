class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age


def create_default_person():
    """Create a default person with name John and age 25."""
    return Person("John", 25)

