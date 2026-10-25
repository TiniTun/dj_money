from django.test import TestCase

from .dashboard.categories import CategoryTree
from .models import ExpenseCategory
from .testing import create_category, create_user


class CategoryTreeTests(TestCase):
    def setUp(self):
        self.user = create_user()

    def test_children_of_not_spending_category_are_excluded(self):
        transfers = create_category(self.user, 'Переводы между своими', is_spending=False)
        child = create_category(self.user, 'Оплата карты', parent=transfers)
        create_category(self.user, 'Продукты')
        self.assertEqual(CategoryTree(self.user).excluded_ids(), {transfers.id, child.id})

    def test_root_of_walks_up_to_top_level(self):
        food = create_category(self.user, 'Еда')
        cafe = create_category(self.user, 'Кафе', parent=food)
        coffee = create_category(self.user, 'Кофе', parent=cafe)
        self.assertEqual(CategoryTree(self.user).root_of(coffee.id), food)

    def test_category_cycle_does_not_hang(self):
        a = create_category(self.user, 'A')
        b = create_category(self.user, 'B', parent=a)
        ExpenseCategory.objects.filter(pk=a.pk).update(parent_category=b)
        tree = CategoryTree(self.user)
        self.assertIn(tree.root_of(a.id), {a, b})
        self.assertEqual(tree.excluded_ids(), set())
