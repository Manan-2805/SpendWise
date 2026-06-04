import factory

from app.models.transaction import Transaction

from .category import CategoryFactory
from .user import UserFactory


class TransactionFactory(factory.Factory):
    class Meta:
        model = Transaction

    amount = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True)
    description = factory.Faker("sentence", nb_words=4)
    transaction_date = factory.Faker("date_this_year")
    type = "expense"
    notes = factory.Faker("paragraph")
    tags = factory.List([factory.Faker("word"), factory.Faker("word")])
    user = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory)
