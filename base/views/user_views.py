from rest_framework import permissions
from django.core.exceptions import ValidationError
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status as statuscode
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from rest_framework.views import APIView
from oauth2_provider.settings import oauth2_settings
from braces.views import CsrfExemptMixin
from oauth2_provider.views.mixins import OAuthLibMixin
from rest_framework.response import Response
from drf_social_oauth2.views import TokenView
from oauth2_provider.models import get_access_token_model, get_application_model, get_refresh_token_model
from oauth2_provider.signals import app_authorized
from base import models
from base import serializers
import json
from twilio.rest import Client
from django.conf import settings
from authy.api import AuthyApiClient
import phonenumbers
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework.generics import GenericAPIView
from oauthlib import common
from django.utils import timezone
from datetime import datetime, timedelta


Application = get_application_model()
AccessToken = get_access_token_model()
RefreshToken = get_refresh_token_model()


authy_api = AuthyApiClient(settings.AUTHY_API_KEY)


client = Client(settings.SOCIAL_AUTH_TWILIO_KEY,
                settings.SOCIAL_AUTH_TWILIO_SECRET)

# channel_configuration = {substitutions:{ email: }}


def verifications(user_destination, via):





    return client.verify \
        .services(settings.TWILIO_VERIFICATION_SID) \
        .verifications \
        .create(
            to=user_destination,
            channel=via,
            channel_configuration={
                'substitutions': {
                    'email': user_destination
                }
            }
                )


def verification_checks(user_destination, token):
    return client.verify \
        .services(settings.TWILIO_VERIFICATION_SID) \
        .verification_checks \
        .create(to=user_destination, code=token)


@api_view(['Get'])
@permission_classes([IsAuthenticated])
def getUserProfile(request):
    user = request.user
    serializer = serializers.CustomUserSerializer(user, many=False)
    return Response(serializer.data)


@api_view(['Get'])
@permission_classes([IsAdminUser])
def getUsers(request):
    users = models.User.objects.all()
    serializer = serializers.UserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def updateUserProfile(request):
    user = request.user
    serializer = serializers.CustomUserSerializer(user, many=False)
    data = request.data
    user.first_name = data['name']
    user.username = data['email']
    user.email = data['email']
    user.authy_phone = data['authy_phone']

    user.save()

    return Response(serializer.data)


# drf_social_oauth2
class updateUserProfileView(TokenView):

    @permission_classes([IsAuthenticated])
    def put(self, request, *args, **kwargs):
        # Use the rest framework `.data` to fake the post body of the django request.
        user = request.user

        serializer = serializers.CustomUserSerializer(user, many=False)

        data = request.data
        user.first_name = data['name']
        user.username = data['email']
        user.email = data['email']
        user.authy_phone = data['authy_phone']

        user.save()

        return Response(serializer.data)


# drf_social_oauth2
class userLoginView(TokenView):
    def post(self, request, *args, **kwargs):
        # Use the rest framework `.data` to fake the post body of the django request.
        mutable_data = request.data.copy()
        request._request.POST = request._request.POST.copy()
        for key, value in mutable_data.items():
            request._request.POST[key] = value
        url, headers, body, status = self.create_token_response(
            request._request)
        if status == 200:
            body = json.loads(body)
            access_token = body.get("access_token")
            if access_token is not None:
                token = get_access_token_model().objects.get(
                    token=access_token)
                app_authorized.send(
                    sender=self, request=request,
                    token=token)
                if not token.user.email_verified:
                    return Response({"error": "Email must be Verified before Login"},
                                    status=statuscode.HTTP_400_BAD_REQUEST)
                user_data = serializers.UserSerializer(token.user).data
                body.update(user_data)
                body = json.dumps(body)
        response = Response(data=json.loads(body), status=status)

        for k, v in headers.items():
            response[k] = v
        return response


class newRegisterView(APIView):
    id = None

    def delete_user(self):
        try:
            user = models.User.objects.get(id=self.id)
            user.delete()
        except Exception as error:
            print("Error: ", error)

    def create_user(self, data):
        serializer = serializers.RegisterSerializerWithToken(data=data)
        try:
            serializer.is_valid(raise_exception=True)
            user = models.User.objects.create(
                first_name=data['name'],
                username=data['email'],
                email=data['email'],
                password=make_password(data['password'])
            )
            self.id = user.id
            return serializer.data
        except ValidationError:
            return Response(serializer.errors, status=statuscode.HTTP_400_BAD_REQUEST)

    def post(self, request, *args, **kwargs):
        # Use the rest framework `.data` to fake the post body of the django request.
        mutable_data = request.data.copy()
        request._request.POST = request._request.POST.copy()
        data = mutable_data
        try:
            serialized_data = self.create_user(data)

            return Response(data={"error": "ERROR"}, status=statuscode.HTTP_400_BAD_REQUEST)

        except Exception as error:
            return Response(data={"error": str(error)}, status=statuscode.HTTP_400_BAD_REQUEST)


class userRegisterView(TokenView):
    id = None

    def delete_user(self):
        try:
            user = models.User.objects.get(id=self.id)
            user.delete()
        except Exception as error:
            print("Error: ", error)

    def create_user(self, data):
        serializer = serializers.RegisterSerializerWithToken(data=data)
        try:
            serializer.is_valid(raise_exception=True)
            user = models.User.objects.create(
                first_name=data['name'],
                username=data['email'],
                email=data['email'],
                password=make_password(data['password'])
            )
            self.id = user.id
            return serializer.data
        except ValidationError:
            return Response(serializer.errors, status=statuscode.HTTP_400_BAD_REQUEST)

    def post(self, request, *args, **kwargs):
        # Use the rest framework `.data` to fake the post body of the django request.
        mutable_data = request.data.copy()
        request._request.POST = request._request.POST.copy()
        data = mutable_data
        try:
            serialized_data = self.create_user(data)
            for key, value in serialized_data.items():
                request._request.POST[key] = value
            url, headers, body, status = self.create_token_response(
                request._request)
            print("status: ", body)
            if status == 401:
                self.delete_user()
                body = json.loads(body)

                return Response(data={"error": str(body)}, status=status)

            if status == 200:
                body = json.loads(body)
                access_token = body.get("access_token")
                if access_token is not None:
                    token = get_access_token_model().objects.get(
                        token=access_token)
                    app_authorized.send(
                        sender=self, request=request,
                        token=token)
                    user_data = serializers.UserSerializer(token.user).data
                    # add user data to token body
                    body.update(user_data)
                    body = json.dumps(body)
            response = Response(data=json.loads(body), status=status)

            for k, v in headers.items():
                response[k] = v
            return response
        except Exception as error:
            return Response(data={"error": str(error)}, status=statuscode.HTTP_400_BAD_REQUEST)


class updateUserNumber(TokenView):
    @permission_classes([IsAuthenticated])
    def put(self, request):
        user = request.user
        serializer = serializers.UserSerializer(user, many=False)
        data = request.data
        number = data['number']

        if (not user.phone_verified and user.number != number):
            verifications(number, 'sms')
            user.number = number
            user.save()
            response = Response(
                data={str("Sending Verification code")}, status=statuscode.HTTP_200_OK)
        elif not user.phone_verified:
            verifications(number, 'sms')
            response = Response(
                data={str("Sending Verification code")}, status=statuscode.HTTP_200_OK)
        else:
            response = Response(data={"error": str(
                "Phone Number is already Verified")}, status=statuscode.HTTP_400_BAD_REQUEST)
        return response


class verifyUserNumber(TokenView):
    @permission_classes([IsAuthenticated])
    def get(self, request):
        user = request.user
        serializer = serializers.UserSerializer(user, many=False)
        data = request.data
        ser = serializer.data
        number = ser['number']
        code = data['code']
        if (not user.phone_verified):
            try:
                valid = verification_checks(number, code).valid
                print(valid)
                user.phone_verified = valid
                user.save()
                response = Response(
                    data={"verified": number}, status=statuscode.HTTP_200_OK)
            except Exception as error:
                print(error)
                response = Response(
                    data={"error": str(error)}, status=statuscode.HTTP_400_BAD_REQUEST)
            return response
        else:
            response = Response(data={"valid": user.phone_verified, "message": str(
                "Phone Number is already Verified")}, status=statuscode.HTTP_200_OK)
        return response


class verifyUserEmail(TokenView):
    def put(self, request):
        data = request.data
        email = data['email']

        verifications(email, 'email')

        return Response(
            data={str("Sending Verification code")}, status=statuscode.HTTP_200_OK)


class confirmUserEmail(TokenView):
    def post(self, request):
        data = request.data
        email = data['email']
        code = data['code']
        try:
            valid = verification_checks(email, code).valid
            print(valid)
            if not valid:
                # verifications(email, 'email')
                return Response(
                    data={"error": "Not Valid Sending Code Again"}, status=statuscode.HTTP_400_BAD_REQUEST)
            try:
                user = models.User.objects.get(email=email)
                user.email_verified = valid
                user.save()
                return Response(
                    data={"verified": email}, status=statuscode.HTTP_200_OK)
            except Exception as error:
                return Response(
                    data={"error": str(error)}, status=statuscode.HTTP_400_BAD_REQUEST)
        except Exception as error:
            return Response(
                data={"error": str(error)}, status=statuscode.HTTP_400_BAD_REQUEST)


class resetPassword(TokenView):
    @permission_classes([IsAuthenticated])
    def put(self, request):
        user = request.user
        data = request.data
        password = make_password(data['password'])

        if (user.phone_verified):
            number = str(user.number)
            print(number)
            verifications(number, 'sms')
            response = Response(data={"message": str(
                "Phone Number is already Verified")}, status=statuscode.HTTP_200_OK)
        else:
            response = Response(data={"error": str(
                "Phone Number is not Verified")}, status=statuscode.HTTP_400_BAD_REQUEST)
        return response


class CustomTokenObtainPairView(TokenView):
    """
    2FA JWT Authentication: Step 0
    """

    # serializer_class = TokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # ret = super().post(request, *args, **kwargs)
        user = models.User.objects.get(username=request.data["username"])
        # check if user has set to true any 2FA method
        # and needs to be re-direct to 2FA verification uri
        if user.is_twofa_on():
            # request 2FA token via sms for user
            sms = authy_api.users.request_sms(user.authy_id, {"force": True})
            if sms.ok():
                return Response(
                    {
                        "message": "SMS request successful. 2FA token verification expected."
                    },
                    status=statuscode.HTTP_206_PARTIAL_CONTENT,
                )
            else:
                return Response(
                    {"error": sms.errors()["message"]},
                    status=statuscode.HTTP_503_SERVICE_UNAVAILABLE,
                )
        # return ret
        mutable_data = request.data.copy()
        request._request.POST = request._request.POST.copy()
        for key, value in mutable_data.items():
            request._request.POST[key] = value
        url, headers, body, status = self.create_token_response(
            request._request)
        if status == 200:
            body = json.loads(body)
            access_token = body.get("access_token")
            if access_token is not None:
                token = get_access_token_model().objects.get(
                    token=access_token)
                app_authorized.send(
                    sender=self, request=request,
                    token=token)
                user_data = serializers.CustomUserSerializer(token.user).data
                body.update(user_data)
                body = json.dumps(body)
        response = Response(data=json.loads(body), status=status)

        for k, v in headers.items():
            response[k] = v
        return response


class PhoneVerificationView(GenericAPIView):
    """
    2FA JWT Authentication: Step 1
    Twilio phone verification view.
    This endpoint will check if user mobile phone number is valid.
    If YES Twilio API send 4 digit verification token via SMS.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.PhoneSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            return Response(status=statuscode.HTTP_204_NO_CONTENT)


class PhoneRegistrationView(GenericAPIView):
    """
    2FA JWT Authentication: Step 2
    Twilio 2FA phone registration view.
    First it will validate if 4 digit tokend sent to user phone number is valid.
    If Twilio verification check pass in next step Twilio API call will register user for 2FA
    If success: user instance will be updated with verified phone number and received from Twilio API authy_id
    """

    serializer_class = serializers.PhoneTokenSerializer
    queryset = models.User.objects.all()
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        data = request.data
        print(user.email)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        phone = phonenumbers.parse(
            str(serializer.validated_data["authy_phone"]), None)
        print(serializer.validated_data)

        authy_user = authy_api.users.create(
            user.email, str(phone.national_number), phone.country_code, True
        )
        print(str(phone.national_number), phone.country_code)

        if authy_user.ok():
            user.authy_id = authy_user.id

            user.authy_phone = serializer.validated_data["authy_phone"]
            user.save()
            return Response(status=statuscode.HTTP_204_NO_CONTENT)
        else:
            return Response(authy_user.errors(), status=statuscode.HTTP_400_BAD_REQUEST)


class AuthyTokenVerifyView(APIView):

    """
    2FA JWT Authentication: Step 3
    Twilio 2FA user authentication view.
    This view verify if Twilio 2FA registered user entered correct 8 digit token.
    Token will be requested by TwoFaTokenObtainPairView only for 2FA registered users
    Is success: user receive refresh and access JWT.
    """

    def post(self, request, *args, **kwargs):
        # ret = request.post(request, *args, **kwargs)
        user = models.User.objects.get(username=request.data["username"])
        validated_data = request.data
        # check if user has 2FA id assigned
        if user.is_twofa_on():
            # verify received 2FA token with Twilio API
            verification = authy_api.tokens.verify(
                user.authy_id, token=request.data["token"]
            )
            if verification.ok():
                serializer = serializers.CustomUserSerializer(user, many=False)

                return Response(serializer.data, status=statuscode.HTTP_200_OK)
            else:
                # return 2FA token verification error
                return Response(
                    {"error": verification.response.json()[
                        "errors"]["message"]},
                    status=statuscode.HTTP_400_BAD_REQUEST,
                )
        else:
            # user has no 2FA authentication methods enabled
            return Response(
                {"error": "User not allowed for 2FA authentication."},
                status=statuscode.HTTP_400_BAD_REQUEST,
            )


class AuthyLogin(APIView):

    """
    2FA JWT Authentication: Step 3
    Twilio 2FA user authentication view.
    This view verify if Twilio 2FA registered user entered correct 8 digit token.
    Token will be requested by TwoFaTokenObtainPairView only for 2FA registered users
    Is success: user receive refresh and access JWT.
    """

    serializer_class = serializers.PhoneTokenSerializer

    def post(self, request, *args, **kwargs):
        data = request.data
        phone = phonenumbers.parse(str(data.get("authy_phone")), None)
        try:
            user = models.User.objects.get(authy_phone=phone)
        # check if user has 2FA id assigned
            if user.is_twofa_on():
                # verify received 2FA token with Twilio API
                verification = authy_api.tokens.verify(
                    user.authy_id, token=request.data["token"]
                )
                if verification.ok():
                    serializer = serializers.CustomUserSerializer(
                        user, many=False)

                    return Response(serializer.data, status=statuscode.HTTP_200_OK)
                else:
                    # return 2FA token verification error
                    return Response(
                        {"error": verification.response.json()[
                            "errors"]["message"]},
                        status=statuscode.HTTP_400_BAD_REQUEST,
                    )
            else:
                # user has no 2FA authentication methods enabled
                return Response(
                    {"error": "User not allowed for 2FA authentication."},
                    status=statuscode.HTTP_400_BAD_REQUEST,
                )
        except Exception as error:
            return Response(data={"error": str(
                "Phone Number Not Found")}, status=statuscode.HTTP_404_NOT_FOUND)


# @api_view(['Get'])
# @permission_classes([IsAuthenticated])
# def testToken(request):
#     user = request.user
#     data = request.data
#     print(data)
#     serializer = serializers.TokenSerializer(data=data)
#     serializer.is_valid()
#     return Response(serializer.data)

class testToken(GenericAPIView):
    """
    TEST TOKEN GENERATION
    """

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.TokenSerializer

    def get(self, request):
        data = request.data
        serializer = self.get_serializer(data=data, user=self.request.user)
        try:
            serializer.is_valid(raise_exception=True)
            print(serializer.validated_data)
            return Response(data=(serializer.validated_data), status=statuscode.HTTP_200_OK)
        except Exception as error:
            return Response(data={"error": str(error)}, status=statuscode.HTTP_400_BAD_REQUEST)
