from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse
import ujson as json
from django.core.files.uploadedfile import InMemoryUploadedFile
import time
from django.http import JsonResponse, HttpResponse
from .WebTable.WebTable import checkKey, getActualAppVersion
from django.core.files.uploadedfile import UploadedFile
import tempfile
import os
from .functions3d import subtract_from_blobs
from django.conf import settings
    
def index(request):
    return render(request, "index.html")

class Auth(APIView):
    def get(self, request):
        response_code = checkKey(user_key=request.query_params.get('key'))
        return Response({"code": response_code})
    
# 0 - версии не совпадают
# 1 - версии совпадают
class AppVersion(APIView):
    def get(self, request):
        cur_app_version = settings.APP_VERSION
        actual_app_version = getActualAppVersion()
        if not (cur_app_version == actual_app_version):
            return Response({"code": 0})
        return Response({"code": 1})
    
class UnionModels(APIView):
    def post(self, request):
        base_file = request.FILES.get('base_stl')
        pattern_file = request.FILES.get('pattern_stl')
        drill_l = float(request.data.get("drill_l"))
        drill_d = float(request.data.get("drill_d"))
        skirt = float(request.data.get("skirt"))
        is_upper = json.loads(request.data.get("is_upper"))
        is_upper = "top" if is_upper==True else "bottom"

        base_bytes = b''.join(base_file.chunks())
        pattern_bytes = b''.join(pattern_file.chunks())
        
        result = subtract_from_blobs(
            model_1_source=base_bytes, 
            model_2_source=pattern_bytes, 
            model_1_file_type="stl", 
            model_2_file_type="stl",
            skirt_position=is_upper,
            skirt_zone=skirt,
            slot_width=drill_d
        )
        
        if result is None or result[0] is None or result[1] is None:
            return JsonResponse({'error': 'Generation failed'}, status=500)
        
        # Кодируем в base64
        import base64
        return JsonResponse({
            'success': True,
            'guide_1': base64.b64encode(result[0]).decode('utf-8'),
            'guide_2': base64.b64encode(result[1]).decode('utf-8'),
        })
    
class saveModel(APIView):
    def post(sefl, request):
        union_1_file = request.FILES.get("union_1_stl")
        union_2_file = request.FILES.get("union_2_stl")
        time_stamp = time.time()
        file_path_1 = f"{os.getcwd()}/save_models/{time_stamp}_union.stl"
        file_path_2 = f"{os.getcwd()}/save_models/{time_stamp}_union_contr.stl"
        with open(file_path_1, 'wb') as f:
            for chunk in union_1_file.chunks():
                f.write(chunk)
        with open(file_path_2, 'wb') as f:
            for chunk in union_2_file.chunks():
                f.write(chunk)
        return Response({"file_path": f"/save_models/{time_stamp}_union.stl, /save_models/{time_stamp}_union_contr.stl"})
