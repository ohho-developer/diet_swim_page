"""
URL configuration for diet_swim_page project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve # serve 뷰 임포트
from django.views.generic import TemplateView
import os

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    path('accounts/', include('accounts.urls')),
    path('api/', include('notification.urls')),
    path('wellness/', include('wellness_checkin.urls')),
]

# Service Worker 파일을 웹사이트 루트에 제공하는 로직 (DEBUG 여부에 따라 다르게)
if settings.DEBUG:
    # 개발 환경에서는 django.views.static.serve를 사용하여 직접 서빙
    # firebase-messaging-sw.js가 BASE_DIR/static/ 에 있다고 가정
    urlpatterns += [
        path('firebase-messaging-sw.js', serve, {
            'path': 'firebase-messaging-sw.js',
            'document_root': os.path.join(settings.BASE_DIR, 'static')
        }),
    ]
    # Django 개발 서버가 /static/ 경로의 파일들을 서빙하도록 하는 설정은 보통 필요 없음
    # (runserver가 기본으로 처리하기 때문)
    # 하지만 명시적으로 두어도 무방합니다.
    # urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

else:
    # 배포 환경 (클라우드타입)에서는 웹 서버가 직접 서빙해야 함
    # 하지만 클라우드타입이 /firebase-messaging-sw.js를 /static/firebase-messaging-sw.js로
    # 리다이렉트/리라이트 하지 않는다면, Django 앱이 직접 처리해야 합니다.
    # 이 경우 TemplateView 또는 커스텀 뷰를 사용
    urlpatterns += [
        path('firebase-messaging-sw.js', TemplateView.as_view(
            template_name='firebase-messaging-sw.js', # templates 폴더 안에 있는 파일 이름
            content_type='application/javascript'
        ), name='firebase_service_worker'),
    ]
    # 배포 환경의 STATIC_ROOT 설정 (웹 서버가 처리할 것임)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)