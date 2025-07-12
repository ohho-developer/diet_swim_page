// 웹 앱 등록 시 받았던 firebaseConfig 객체에서 messagingSenderId 만 필요합니다.
// 다른 firebaseConfig 값들도 여기에 넣어줄 수 있습니다.
importScripts('https://www.gstatic.com/firebasejs/11.10.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/11.10.0/firebase-messaging-compat.js');

// TODO: Replace the following with your app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyDRif0AxGNYsiDPJcTPpOf5sFypSX8Uhn4",
    authDomain: "blooming-swim.firebaseapp.com",
    projectId: "blooming-swim",
    storageBucket: "blooming-swim.firebasestorage.app",
    messagingSenderId: "81211203206",
    appId: "1:81211203206:web:ad6359c088db43d5f57b07",
    measurementId: "G-FJ85C6LFQW"
};

// Initialize the Firebase app in the service worker by passing in
// your app's configuration.
firebase.initializeApp(firebaseConfig);

// Retrieve an instance of Firebase Messaging so that it can handle background
// messages.
const messaging = firebase.messaging();

// iOS Safari 감지 (Service Worker 환경에서는 window 사용 불가)
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
const isSafari = /Safari/.test(navigator.userAgent) && !/Chrome/.test(navigator.userAgent);
// Service Worker에서는 standalone 정보를 직접 확인할 수 없으므로 제거
const isStandalone = false;

// 중복 메시지 방지를 위한 캐시
const processedMessages = new Set();

// 백그라운드 메시지 수신 처리 (iOS Safari 강화)
messaging.onBackgroundMessage((payload) => {
    console.log('[firebase-messaging-sw.js] Received background message ', payload);
    
    // 중복 메시지 체크
    const messageId = payload.data?.message_id || payload.notification?.tag || 'default';
    if (processedMessages.has(messageId)) {
        console.log('[firebase-messaging-sw.js] Duplicate message detected, skipping:', messageId);
        return;
    }
    
    // 메시지 ID를 캐시에 추가 (최대 100개 유지)
    processedMessages.add(messageId);
    if (processedMessages.size > 100) {
        const firstKey = processedMessages.values().next().value;
        processedMessages.delete(firstKey);
    }
    
    console.log('[firebase-messaging-sw.js] Processing message:', messageId);
    
    // 브라우저 탭 간 중복 알림 방지: 다른 탭에 이미 알림이 표시되었는지 확인
    const notificationTag = 'blooming-swim-notification';
    self.registration.getNotifications({ tag: notificationTag }).then((notifications) => {
        if (notifications.length > 0) {
            console.log('[firebase-messaging-sw.js] Notification already exists, skipping');
            return;
        }
    
    // iOS Safari 특별 처리
    if (isIOS && isSafari) {
        console.log('[iOS Safari] Processing background message');
        
        // iOS에서 알림 표시 방식 개선
        const notificationTitle = payload.notification?.title || payload.data?.title || 'Blooming Swim';
        const notificationBody = payload.notification?.body || payload.data?.body || '새로운 알림이 있습니다';
        
        const notificationOptions = {
            body: notificationBody,
            icon: '/static/img/hochul.png',
            badge: '/static/img/hochul.png',
            data: payload.data || {},
            tag: 'blooming-swim-notification',
            requireInteraction: true,
            actions: [
                {
                    action: 'open',
                    title: '열기'
                },
                {
                    action: 'close',
                    title: '닫기'
                }
            ],
            // iOS Safari 최적화
            silent: false,
            vibrate: [200, 100, 200],
            timestamp: Date.now()
        };

        // iOS PWA 모드에서 추가 옵션
        if (isStandalone) {
            notificationOptions.actions.push({
                action: 'add_to_home',
                title: '홈에 추가'
            });
        }

        return self.registration.showNotification(notificationTitle, notificationOptions);
    } else {
        // 일반 브라우저 처리
        const notificationTitle = payload.notification?.title || payload.data?.title || 'Blooming Swim';
        const notificationBody = payload.notification?.body || payload.data?.body || '새로운 알림이 있습니다';
        
        const notificationOptions = {
            body: notificationBody,
            icon: '/static/img/hochul.png',
            badge: '/static/img/hochul.png',
            data: payload.data || {},
            tag: 'blooming-swim-notification',
            requireInteraction: true,
            actions: [
                {
                    action: 'open',
                    title: '열기'
                }
            ]
        };

        return self.registration.showNotification(notificationTitle, notificationOptions);
    }
    });
});

// 알림 클릭 시 처리 (iOS Safari 강화)
self.addEventListener('notificationclick', (event) => {
    console.log('Notification click received.', event);
    event.notification.close(); // 알림 닫기

    const clickData = event.notification.data; // 페이로드의 data 필드 접근
    const action = event.action; // 클릭된 액션

    let targetUrl = 'https://bloomingswim.designusplus.com'; // 기본 이동 URL

    // 백엔드에서 보낸 data 페이로드에 'url' 필드가 있다면 해당 URL을 사용
    if (clickData && clickData.url) {
        targetUrl = clickData.url;
    }

    // 액션별 처리
    if (action === 'close') {
        return; // 아무것도 하지 않음
    } else if (action === 'add_to_home' && isIOS && isSafari) {
        // iOS PWA 홈 추가 안내
        targetUrl = 'https://bloomingswim.designusplus.com/pwa-install-guide';
    }

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // 이미 열려있는 탭이 있다면 해당 탭으로 포커스
                for (const client of clientList) {
                    if (client.url === targetUrl && 'focus' in client) {
                        return client.focus();
                    }
                }
                // 없으면 새 탭으로 열기
                return clients.openWindow(targetUrl);
            })
    );
});

// 서비스 워커 설치 시 캐시 처리
self.addEventListener('install', (event) => {
    console.log('[Service Worker] Installing...');
    self.skipWaiting();
});

// 서비스 워커 활성화 시 처리
self.addEventListener('activate', (event) => {
    console.log('[Service Worker] Activating...');
    event.waitUntil(
        clients.claim()
    );
});

// iOS Safari에서는 onBackgroundMessage만 사용하므로 push 이벤트 리스너 제거
// 중복 알림 방지를 위해 push 이벤트는 처리하지 않음
console.log('[Service Worker] iOS Safari detected - using onBackgroundMessage only'); 