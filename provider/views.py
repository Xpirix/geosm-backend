from django.shortcuts import render

# Create your views here.
from .models import Vector
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.parsers import FileUploadParser
from rest_framework.response import Response
from rest_framework.generics import (ListCreateAPIView,RetrieveUpdateDestroyAPIView,)
from rest_framework.views import APIView
from rest_framework import status
from django.db.models import Count
from geosmBackend.type import httpResponse

from .serializers import VectorProviderSerializer
from collections import defaultdict
import traceback
# Create your views here.

class vectorProviderView(APIView):
    """
        View to list all vector provider, add a vector provider usernames = [user.username for user in User.objects.all()]
        return Response(usernames)
    """
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, *args, **kwargs):
        """ get all vector provider """
        return Response([VectorProviderSerializer(vector).data for vector in Vector.objects.all()],status=status.HTTP_200_OK)
    
    def post(self, request, *args, **kwargs):
        """ store a new vector providor """
        vp_serializer = VectorProviderSerializer(data=request.data)
        # if 'table' not in  request.data or 'shema' not in  request.data:
            # request._mutable = True
            # request.data.__setitem__('state','action_require')

        if vp_serializer.is_valid():
            vp_serializer.save()
            return Response(vp_serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(vp_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        """ Delete vector providers """
        try:
            provider_vector_ids= request.data['provider_vector_ids']
            vector_providers = Vector.objects.filter(pk__in=provider_vector_ids)
            vector_providers.delete()
            return Response(httpResponse(False).__dict__,status=status.HTTP_200_OK)
        except :
            traceback.print_exc()
            return Response(httpResponse(True,'An unexpected error has occurred').__dict__,status=status.HTTP_400_BAD_REQUEST)

class searchVectorProvider(APIView):
    """
        View to search a vector provider
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        searchWord = request.data['search_word']
        responseQuerry = []
        for vector in Vector.objects.raw("SELECT * FROM provider_vector WHERE strpos(unaccent(lower(name)),unaccent(lower('"+searchWord+"')))>0 Limit 20 "):
            responseQuerry.append(VectorProviderSerializer(vector).data)

        return Response(responseQuerry,status=status.HTTP_200_OK)


class vectorProviderDetailView(RetrieveUpdateDestroyAPIView):
    """ View get a vector provider, update or delete it """
    queryset=Vector.objects.all()
    serializer_class=VectorProviderSerializer
    permission_classes=[permissions.IsAuthenticated]