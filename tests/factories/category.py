import factory

from app.models.category import Category

from .user import UserFactory


class CategoryFactory(factory.Factory):
    class Meta:
        model = Category

    name = factory.Faker("word")
    description = factory.Faker("sentence")
    color = factory.Faker("hex_color")
    icon = "home"
    type = "expense"
    is_system = False
    user = factory.SubFactory(UserFactory)
