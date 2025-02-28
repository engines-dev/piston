from utils import is_even
from data import Person


def greet_person(person):
    """Greet a person with a message based on their age."""
    greeting = f"Hello, {person.name}!"
    if is_even(person.age):
        greeting += " You have an even age."
    return greeting


def run():
    bob = Person("Bob", 30)
    print(greet_person(bob))


if __name__ == "__main__":
    run()

