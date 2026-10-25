from money.models import ExpenseCategory


class CategoryTree:
    """The user's expense categories in memory, for walking up to parents without a query per node."""

    def __init__(self, user):
        self.categories = {c.id: c for c in ExpenseCategory.objects.filter(user=user)}

    def _ancestors(self, category_id):
        """The category itself and its parents up to the top; stops if the parents form a cycle."""
        seen = set()
        while category_id in self.categories and category_id not in seen:
            seen.add(category_id)
            yield self.categories[category_id]
            category_id = self.categories[category_id].parent_category_id

    def root_of(self, category_id):
        *_, root = self._ancestors(category_id)
        return root

    def excluded_ids(self):
        """Categories marked is_spending=False, plus all their descendants."""
        return {
            category_id for category_id in self.categories
            if any(not c.is_spending for c in self._ancestors(category_id))
        }
