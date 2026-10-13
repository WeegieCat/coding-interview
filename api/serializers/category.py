from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from api.models.category import Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "company", "name", "parent_category", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
        validators = [
            UniqueTogetherValidator(
                queryset=Category.objects.all(),
                fields=["company", "name"],
                message="同一企業内に同名のカテゴリが既に存在します。",
            )
        ]


    def validate(self, attrs):
        if self.instance is not None and "company" in attrs and attrs["company"] != self.instance.company:
            raise serializers.ValidationError({"company": "作成後に企業を変更することはできません。"})

        company = attrs.get("company", getattr(self.instance, "company", None))
        parent = attrs.get("parent_category", getattr(self.instance, "parent_category", None))

        if parent is None:
            return attrs

        if parent.company_id != company.id:
            raise serializers.ValidationError({"parent_category": "親カテゴリは同一企業のカテゴリを指定してください。"})

        if self.instance is not None:
            seen = set()
            node = parent
            while node is not None and node.pk not in seen:
                if node.pk == self.instance.pk:
                    raise serializers.ValidationError({"parent_category": "循環する親子関係は指定できません。"})
                seen.add(node.pk)
                node = node.parent_category
        return attrs
