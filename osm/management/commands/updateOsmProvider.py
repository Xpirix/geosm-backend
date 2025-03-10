from django.core.management import color
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, Error
from django.http.request import QueryDict
from psycopg2.extensions import AsIs
import traceback
from django.conf import settings
from provider.models import Vector
from osm.models import Querry
from django.core.files import File
import pathlib
from os.path import join, exists, basename
from os import makedirs, name, path
from shutil import copyfile
from csv import reader
from django.db import transaction
import json
from typing import Callable, Any, List

class Command(BaseCommand):
    help = 'Update OSM provider'

    def handle(self, *args, **options):
        count = Querry.objects.filter(auto_update=True).count()
        i=1
        for querry in Querry.objects.filter(auto_update=True):
            osmQuerry:Querry=querry
            osmQuerry.save()
            self.stdout.write(self.style.SUCCESS(str(i)+'/'+str(count)))
            i=1+i
        self.stdout.write(self.style.SUCCESS('All the OSM querries, have been successfuly updated'))  