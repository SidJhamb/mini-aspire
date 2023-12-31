from django.contrib.auth.models import AnonymousUser
from django.db.models import Sum
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.generics import GenericAPIView
from loan import serializers
from rest_framework.response import Response
from rest_framework import status

from .serializers import (
    UserSerializer,
    LoanListSerializer
)
from core.backend import BasicRequestBodyAuthentication
from core.models import (
    User,
    Loan,
    Repayment,
    LoanStatus,
    RepaymentStatus
)
from datetime import timedelta

INVALID_USER_CREDENTIALS = 'Invalid/missing user credentials in the request header'


class AuthMixin:
    @staticmethod
    def authenticate_request(request):
        return not isinstance(request.user, AnonymousUser)

    @staticmethod
    def authenticate_admin_request(request):
        return not isinstance(request.user, AnonymousUser) and request.user.is_admin


@api_view(['PUT'])
@authentication_classes([BasicRequestBodyAuthentication])
def loan_approval(request, loan_id):
    """Handles loan approvals by the admin user."""
    try:
        if not AuthMixin.authenticate_admin_request(request):
            return Response(data={'error': INVALID_USER_CREDENTIALS}, status=status.HTTP_401_UNAUTHORIZED)

        loan = Loan.objects.get(id=loan_id)
        loan.status = LoanStatus.APPROVED
        loan.save(update_fields=['status'])
        return Response(data={'message': "Loan, with ID {} is approved.".format(loan_id)})
    except Loan.DoesNotExist:
        return Response({'error': "Loan with ID {} does not exist.".format(loan_id)},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as ex:
        return Response({'error': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserView(GenericAPIView):
    serializer_class = UserSerializer

    def post(self, request):
        """Handles creation of new user records."""
        try:
            user_name = request.data.get('user_name')
            is_admin = request.data.get('is_admin')

            if not user_name:
                return Response({'error': 'Please provide the user_name in request body.'},
                                status=status.HTTP_400_BAD_REQUEST)

            if not is_admin:
                return Response({'error': 'Please provide the is_admin flag in request body.'},
                                status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.get(user_name=user_name)
            return Response({'error': 'User with this ID already exists.'}, status=status.HTTP_409_CONFLICT)
        except User.DoesNotExist:
            user = User.objects.create_user(user_name=user_name, is_admin=is_admin)
            serializer = self.serializer_class(user)
            return Response(serializer.data, status=201)
        except Exception as ex:
            return Response({'error': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoanView(GenericAPIView, AuthMixin):
    serializer_class = serializers.LoanSerializer
    authentication_classes = (BasicRequestBodyAuthentication,)

    def get(self, request):
        """Handles retrieving ALL loan records for a particular user."""
        try:
            if not self.authenticate_request(request):
                return Response(data={'error': INVALID_USER_CREDENTIALS}, status=status.HTTP_401_UNAUTHORIZED)

            loans = Loan.objects.filter(user_id=request.user.id)
            serializer = LoanListSerializer(loans, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as ex:
            return Response({'error': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """Handles creation of new loan record for a particular user."""
        try:
            if not self.authenticate_request(request):
                return Response(data={"error": INVALID_USER_CREDENTIALS}, status=status.HTTP_401_UNAUTHORIZED)

            loan_data = self.serializer_class(data=request.data)

            if loan_data.is_valid():
                loan_amount = loan_data.validated_data['amount']
                number_of_terms = loan_data.validated_data['terms']
                loan = Loan.objects.create(user=request.user, amount=loan_amount, terms=number_of_terms)
                for i in range(number_of_terms):
                    due_date = loan.created_date + timedelta(weeks=i+1)
                    repayment = Repayment.objects.create(loan=loan, amount=loan_amount/number_of_terms, due_date=due_date)
                return Response(data={'id': loan.id}, status=status.HTTP_200_OK)
            else:
                return Response({'error': str(loan_data.errors)}, status=status.HTTP_400_BAD_REQUEST)
        except serializers.ValidationError as ex:
            return Response({'error': str(ex)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as ex:
            return Response({'error': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RepaymentView(GenericAPIView, AuthMixin):
    serializer_class = serializers.RepaymentSerializer
    authentication_classes = (BasicRequestBodyAuthentication,)

    @staticmethod
    def balance_repayments(loan):
        """
        This balances the pending repayment ampounts if the incoming repayment amount is more than the expected value.
        """
        paid_repayments_amount = Repayment.objects.filter(status=RepaymentStatus.PAID, loan_id=loan.id).aggregate(Sum('amount'))['amount__sum']
        balance_amount = loan.amount - paid_repayments_amount

        pending_repayments = Repayment.objects.filter(loan_id=loan.id, status=RepaymentStatus.PENDING).count()
        if pending_repayments > 0:
            new_unpaid_rep_amount = balance_amount/pending_repayments
            Repayment.objects.filter(status=RepaymentStatus.PENDING).update(amount=new_unpaid_rep_amount)

    @staticmethod
    def mark_loan_paid(loan):
        """This marks a loan as paid if all the repayments against it have been marked as paid."""
        if not Repayment.objects.filter(loan_id=loan.id, status=RepaymentStatus.PENDING).exists():
            loan.status = LoanStatus.PAID
            loan.save(update_fields=['status'])

    def put(self, request, loan_id, repayment_id):
        """Handles making repayments for a particular loan."""
        try:
            if not self.authenticate_request(request):
                return Response(data={"error": INVALID_USER_CREDENTIALS}, status=status.HTTP_401_UNAUTHORIZED)

            loan = Loan.objects.get(id=loan_id)
            repayment = Repayment.objects.get(loan_id=loan_id, id=repayment_id)

            # if not is_date_difference_less_than_one_week(loan.created_date, repayment.due_date):
            #     return Response({'error': "error in approving, its past the due date"}, status=HTTP_400_BAD_REQUEST)

            if loan.status == LoanStatus.PENDING:
                return Response({'error': "The loan is not approved yet. Repayments can only be done for approved loans"},
                                status=status.HTTP_400_BAD_REQUEST)

            if loan.status == LoanStatus.PAID:
                return Response({'error': "All repayments for this loan are already complete"}, status=status.HTTP_200_OK)

            repayment_data = self.serializer_class(data=request.data)

            if repayment_data.is_valid():
                repayment_amount = repayment_data.validated_data['amount']

                if repayment_amount < repayment.amount:
                    return Response({'error': "The repayment amount is less than expected. The minimum expected"
                                              "amount for this repayment is {}.".format(str(repayment.amount))},
                                    status=status.HTTP_400_BAD_REQUEST)

                repayment.status = RepaymentStatus.PAID
                repayment.amount = repayment_amount
                repayment.save(update_fields=['status', 'amount'])

                self.balance_repayments(loan)
                self.mark_loan_paid(loan)

                return Response(data={'message': "Repayment successfully completed."}, status=status.HTTP_200_OK)
            else:
                return Response({'error': str(repayment_data.errors)}, status=status.HTTP_400_BAD_REQUEST)
        except Loan.DoesNotExist:
            return Response({'error': "Loan with ID {} does not exist.".format(loan_id)},
                            status=status.HTTP_404_NOT_FOUND)
        except Repayment.DoesNotExist:
            return Response({'error': "Repayment with ID {} does not exist.".format(repayment_id)},
                            status=status.HTTP_404_NOT_FOUND)
        except serializers.ValidationError as ex:
            return Response({'error': str(ex)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as ex:
            return Response({'error': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
