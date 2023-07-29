"""
Database models.
"""
from django.contrib.auth.base_user import BaseUserManager
from django_enumfield import enum
from django.db import models


class LoanStatus(enum.Enum):
    PENDING = 0
    APPROVED = 1
    PAID = 2

    @classmethod
    def get_status(cls, type_id):
        return cls.get(type_id).name


class RepaymentStatus(enum.Enum):
    PENDING = 0
    PAID = 1

    @classmethod
    def get_status(cls, type_id):
        return cls.get(type_id).name


class UserManager(BaseUserManager):
    def create_user(self, user_name):
        user = self.model(user_name=user_name)
        user.save(using=self._db)
        return user


class User(models.Model):
    user_name = models.CharField(max_length=50, unique=True)
    objects = UserManager()


class Loan(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    amount = models.IntegerField()
    terms = models.IntegerField()
    created_date = models.DateField(auto_now_add=True)
    status = enum.EnumField(LoanStatus, default=LoanStatus.PENDING)


class Repayment(models.Model):
    loan = models.ForeignKey('Loan', related_name='repayments', on_delete=models.CASCADE)
    amount = models.IntegerField()
    status = enum.EnumField(RepaymentStatus, default=RepaymentStatus.PENDING)
    due_date = models.DateField()


