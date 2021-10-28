from .models import Vector, Style
from osm.models import Querry
from django.core.exceptions import ObjectDoesNotExist
from typing import NamedTuple
from django.db.models import Count, Q
import re
from django.db import connection, Error
from psycopg2.extensions import AsIs
from .qgis.manageVectorLayer import addVectorLayerFomPostgis, removeLayer
from .qgis.manageStyle import getQMLStyleOfLayer
from django.conf import settings
from os.path import join
from geosmBackend.type import OperationResponse, AddVectorLayerResponse, GetQMLStyleOfLayerResponse
from django.core.files import File
from django.core.files.base import ContentFile

import traceback

DATABASES = settings.DATABASES
OSMDATA = settings.OSMDATA
class TableAndSchema(NamedTuple):
    """ represent the table and shema of a provider """
    table:str
    shema:str


class manageOsmDataSource():
    """ create or delete before creating a table with an osm querry """
    def __init__(self, provider_vector:Vector):
        self.provider_vector:Vector = provider_vector

    def deleteDataSource(self)->OperationResponse:
        """ Delete and osm datasource by droping his table """
        response=OperationResponse(
            error=False,
            msg="",
            description="",
        )

        self._getTableAndSchema()

        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS "+self.tableAndShema.shema+"."+self.tableAndShema.table)
                response.error = False
                return response
        except Error as errorIdentifier :
            traceback.print_exc()
            response.error = True
            response.msg = ' Can not drop the table '
            response.description = str(errorIdentifier)
            return response


    def updateDataSource(self, osm_querry:Querry)->OperationResponse:
        """ update an osm datsource """

        response=OperationResponse(
            error=False,
            msg="",
            description="",
        )
        self.osm_querry:Querry = osm_querry
        self._getTableAndSchema()

        createOrReplaceTableResponse = self._createOrReplaceTable()

        if createOrReplaceTableResponse.error == False:
            if createOrReplaceTableResponse.data['extent']:
                self.provider_vector.extent = createOrReplaceTableResponse.data['extent']
            self.provider_vector.count = createOrReplaceTableResponse.data['count']
            self.provider_vector.save()

        return createOrReplaceTableResponse

    def createDataSource(self, osm_querry:Querry)->AddVectorLayerResponse:
        """ create an osm datsource, after add it to an QGIS project """

        response=AddVectorLayerResponse(
            error=False,
            msg="",
            description="",
            pathProject="",
            layerName="",
        )

        self.osm_querry:Querry = osm_querry
        self._getTableAndSchema()
        
        createOrReplaceTableResponse = self._createOrReplaceTable()

        if createOrReplaceTableResponse.error == False:
            qgis_project = 'projet'+'_'+str(int(Vector.objects.count()/5))+'.qgs'
            
            createOSMDataSourceResponse =  addVectorLayerFomPostgis(
                DATABASES['default']['HOST'],
                DATABASES['default']['PORT'],
                DATABASES['default']['NAME'],
                DATABASES['default']['USER'],
                DATABASES['default']['PASSWORD'],
                self.provider_vector.shema,
                self.provider_vector.table,
                'geom',
                'osm_id',
                self.provider_vector.table,
                qgis_project
            )

            if createOSMDataSourceResponse.error == False:
                if createOrReplaceTableResponse.data['extent']:
                    self.provider_vector.extent = createOrReplaceTableResponse.data['extent']
                self.provider_vector.count = createOrReplaceTableResponse.data['count']

                self.provider_vector.path_qgis = qgis_project
                self.provider_vector.url_server = OSMDATA['url_qgis_server_prefix']+qgis_project
                self.provider_vector.id_server = createOSMDataSourceResponse.layerName
                self.provider_vector.save()

                try:
                    f = open(join(OSMDATA['qml_default_path'],'default-'+self.provider_vector.geometry_type+'.qml'))
                    myfile = File(f)
                    default_style = Style(
                        name='default',
                        qml_file=myfile,
                        provider_vector_id=self.provider_vector
                    )
                    default_style.save()
                except Exception as e :
                        print(str(e),'error')
                        
                

            return createOSMDataSourceResponse

        else:
            response.error = True
            response.msg = createOrReplaceTableResponse.msg
            response.description = createOrReplaceTableResponse.description
            return response
    
    def _getTableAndSchema(self) ->TableAndSchema:
        """ 
            Get table or shema of the table of this vector provider in databse
            will check if table and shema already exist in the vector provider properties and return them
            If they not exist, will create them randomnly
        """
        shema = None
        table = None
        if self.provider_vector.shema:
            shema = self.provider_vector.shema
        else:
            shema = 'osm_tables'

        if self.provider_vector.table:
            table = self.provider_vector.table
        else:
            table = re.sub('[^A-Za-z0-9]+', '', self.provider_vector.name).lower()
            i= 0

            while Vector.objects.annotate( num_table=Count('table',filter=Q(table=table) ) )[0].num_table != 0:
                table = re.sub('[^A-Za-z0-9]+', '', self.provider_vector.name).lower()+'_'+str(i)
                i += 1 

        self.tableAndShema:TableAndSchema = TableAndSchema(table, shema)
        return self.tableAndShema

    def _createOrReplaceTable(self) -> OperationResponse:
        """
            Create a table in a shema of replace it with new osm querry:
            -  If the schema does not exist, create it
            - drop the table if exist
            - create table as the osm querry sql
            - update table, shema, extent, total area, total lenght and count of the vector provider
        """

        response=OperationResponse(
            error=False,
            msg="",
            description="",
            data={
                'extent':None,
                'count':0
            }
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = '"+self.tableAndShema.shema+"'")
           
            if cursor.rowcount == 0:
                cursor.execute("CREATE SCHEMA "+self.tableAndShema.shema)

        with connection.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS "+self.tableAndShema.shema+'.'+self.tableAndShema.table)

        try:
            with connection.cursor() as cursor:
                cursor.execute("CREATE TABLE  "+self.tableAndShema.shema+"."+self.tableAndShema.table+" AS "+self.osm_querry.sql)
                cursor.execute("CREATE INDEX "+ self.tableAndShema.table+"_geometry_idx ON " + self.tableAndShema.shema+"."+self.tableAndShema.table+" USING GIST(geom) ")
                if self.provider_vector.geometry_type == 'Point':
                    cursor.execute("ALTER TABLE "+ self.tableAndShema.shema+"."+self.tableAndShema.table+" ALTER COLUMN geom TYPE geometry(Point,4326) USING ST_centroid(geom); ")
            
            with connection.cursor() as cursor:
                cursor.execute("select min(ST_XMin(geom)) as l,min(ST_YMin(geom)) as b,max(ST_XMax(geom)) as r,max(ST_YMax(geom)) as t, count(*) as count from "+self.tableAndShema.shema+"."+self.tableAndShema.table)
                responseExtent = cursor.fetchall()[0]
                response.data['extent']=[
                    responseExtent[0],
                    responseExtent[1],
                    responseExtent[2],
                    responseExtent[3]
                ]
               
                response.data['count']= int(responseExtent[4])

        except Error as errorIdentifier :
            response.error = True
            response.msg = ' Can not create the table '+self.tableAndShema.table
            response.description = str(errorIdentifier)
            return response

        self.provider_vector.table = self.tableAndShema.table
        self.provider_vector.shema = self.tableAndShema.shema
        self.provider_vector.save()

        return  response
