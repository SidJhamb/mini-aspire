from rest_framework import serializers

from core.models import (
    User,
    Loan,
    Repayment,
    RepaymentStatus,
    LoanStatus
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('user_name',)


class LoanSerializer(serializers.Serializer):
    amount = serializers.IntegerField()
    terms = serializers.IntegerField()


class RepaymentSerializer(serializers.Serializer):
    amount = serializers.IntegerField()


class RepaymentListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return RepaymentStatus.get_status(obj.status)

    class Meta:
        model = Repayment
        fields = ('id', 'amount', 'status', 'due_date')


class LoanListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    repayments = RepaymentListSerializer(many=True, read_only=True)

    def get_status(self, obj):
        return LoanStatus.get_status(obj.status)

    class Meta:
        model = Loan
        fields = ('id', 'amount', 'terms', 'repayments', 'status')
