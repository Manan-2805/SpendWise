import factory

from app.core.security import hash_password
from app.models.user import User


class UserFactory(factory.Factory):
    class Meta:
        model = User

    email = factory.Faker("email")
    username = factory.Faker("user_name")
    hashed_password = factory.LazyFunction(lambda: hash_password("TestPassword123!"))
    is_active = True
    is_verified = False
    is_superuser = False
