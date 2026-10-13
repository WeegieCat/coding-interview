import uuid

from rest_framework import status
from rest_framework.test import APITestCase

from api.models.category import Category
from api.models.company import Company


class CategoryViewTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="A社")
        self.other_company = Company.objects.create(name="B社")
        self.list_url = "/api/categories/"

    def detail_url(self, pk):
        return f"{self.list_url}{pk}/"

    def create_category(self, name="食品", company=None, parent=None):
        return Category.objects.create(name=name, company=company or self.company, parent_category=parent)

    # ---- list ----
    def test_list(self):
        # 一覧が作成順で返る
        self.create_category("a")
        self.create_category("b")
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual([c["name"] for c in res.data], ["a", "b"])

    def test_list_empty(self):
        # 0件のときは空配列が返る
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [])

    # ---- retrieve ----
    def test_retrieve(self):
        # 1件を取得でき、各項目の値が正しい
        category = self.create_category()
        res = self.client.get(self.detail_url(category.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], str(category.id))
        self.assertEqual(res.data["name"], "食品")
        self.assertEqual(res.data["company"], self.company.id)
        self.assertIsNone(res.data["parent_category"])

    def test_retrieve_not_found(self):
        # 存在しないIDは404
        res = self.client.get(self.detail_url(uuid.uuid4()))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # ---- create ----
    def test_create(self):
        # 作成でき、DBに保存される
        res = self.client.post(self.list_url, {"company": self.company.id, "name": "食品"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Category.objects.filter(id=res.data["id"], name="食品", company=self.company).exists())

    def test_create_with_parent(self):
        # 同一企業の親カテゴリを指定して作成できる
        parent = self.create_category("親")
        res = self.client.post(
            self.list_url,
            {"company": self.company.id, "name": "子", "parent_category": parent.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["parent_category"], parent.id)

    def test_create_missing_required_fields(self):
        # 必須項目(company, name)が無い場合は400
        res = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("company", res.data)
        self.assertIn("name", res.data)

    def test_create_blank_name(self):
        # 空白のみの名前は400
        res = self.client.post(self.list_url, {"company": self.company.id, "name": "   "}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", res.data)

    def test_create_name_too_long(self):
        # 255文字を超える名前は400
        res = self.client.post(self.list_url, {"company": self.company.id, "name": "a" * 256}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", res.data)

    def test_create_duplicate_name_in_same_company(self):
        # 同一企業内の同名は400で、件数は増えない
        self.create_category("食品")
        res = self.client.post(self.list_url, {"company": self.company.id, "name": "食品"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Category.objects.count(), 1)

    def test_create_same_name_in_other_company(self):
        # 別企業であれば同名でも作成できる
        self.create_category("食品")
        res = self.client.post(self.list_url, {"company": self.other_company.id, "name": "食品"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_create_company_not_found(self):
        # 存在しない企業を指定した場合は400
        res = self.client.post(self.list_url, {"company": str(uuid.uuid4()), "name": "食品"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("company", res.data)

    def test_create_parent_in_other_company(self):
        # 他社のカテゴリを親に指定した場合は400
        parent = self.create_category("親", company=self.other_company)
        res = self.client.post(
            self.list_url,
            {"company": self.company.id, "name": "子", "parent_category": parent.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent_category", res.data)

    # ---- update ----
    def test_update(self):
        # PUTで名前を更新できる
        category = self.create_category("旧")
        res = self.client.put(
            self.detail_url(category.id), {"company": self.company.id, "name": "新"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        category.refresh_from_db()
        self.assertEqual(category.name, "新")

    def test_partial_update(self):
        # PATCHでは送った項目だけ更新され、親は保持される
        parent = self.create_category("親")
        category = self.create_category("子", parent=parent)
        res = self.client.patch(self.detail_url(category.id), {"name": "子2"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        category.refresh_from_db()
        self.assertEqual(category.name, "子2")
        self.assertEqual(category.parent_category, parent)

    def test_update_to_duplicate_name(self):
        # 同一企業内の既存の名前への変更は400
        self.create_category("a")
        category = self.create_category("b")
        res = self.client.patch(self.detail_url(category.id), {"name": "a"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_keep_own_name(self):
        # 自分の名前のままの更新は重複扱いにならない
        category = self.create_category("a")
        res = self.client.patch(self.detail_url(category.id), {"name": "a"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_update_parent_to_self(self):
        # 自分自身を親に指定した場合は400
        category = self.create_category("a")
        res = self.client.patch(self.detail_url(category.id), {"parent_category": category.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent_category", res.data)

    def test_update_parent_to_descendant(self):
        # 自分の子孫を親に指定した場合(循環参照)は400
        parent = self.create_category("親")
        child = self.create_category("子", parent=parent)
        grandchild = self.create_category("孫", parent=child)
        res = self.client.patch(self.detail_url(parent.id), {"parent_category": grandchild.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_not_found(self):
        # 存在しないIDの更新は404
        res = self.client.patch(self.detail_url(uuid.uuid4()), {"name": "x"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_ignores_read_only_fields(self):
        # 読み取り専用のidを送っても無視される
        category = self.create_category()
        res = self.client.patch(self.detail_url(category.id), {"id": str(uuid.uuid4())}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], str(category.id))

    def test_update_company_not_allowed(self):
        # 作成後の企業変更は400で、企業は変わらない
        category = self.create_category()
        res = self.client.patch(self.detail_url(category.id), {"company": self.other_company.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("company", res.data)
        category.refresh_from_db()
        self.assertEqual(category.company, self.company)

    def test_update_clear_parent(self):
        # nullを送ると親カテゴリを解除できる
        parent = self.create_category("親")
        category = self.create_category("子", parent=parent)
        res = self.client.patch(self.detail_url(category.id), {"parent_category": None}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        category.refresh_from_db()
        self.assertIsNone(category.parent_category)

    # ---- destroy ----
    def test_destroy(self):
        # 削除でき、DBから消える
        category = self.create_category()
        res = self.client.delete(self.detail_url(category.id))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(id=category.id).exists())

    def test_destroy_parent_sets_child_parent_null(self):
        # 親を削除すると子は残り、子の親がNULLになる
        parent = self.create_category("親")
        child = self.create_category("子", parent=parent)
        res = self.client.delete(self.detail_url(parent.id))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        child.refresh_from_db()
        self.assertIsNone(child.parent_category)

    def test_destroy_not_found(self):
        # 存在しないIDの削除は404
        res = self.client.delete(self.detail_url(uuid.uuid4()))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)