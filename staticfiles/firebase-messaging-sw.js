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

        // 백그라운드 메시지 수신 처리
        messaging.onBackgroundMessage((payload) => {
            console.log('[firebase-messaging-sw.js] Received background message ', payload);
            // Customize notification here
            const notificationTitle = payload.notification.title;
            const notificationOptions = {
                body: payload.notification.body,
                icon: '/static/img/hochul.png', // 알림 아이콘 (필수!)
                data: payload.data, // 추가 데이터
                // 기타 옵션: image, tag, requireInteraction, actions 등
            };

            self.registration.showNotification(notificationTitle, notificationOptions);
        });

        // 알림 클릭 시 처리 (선택 사항)
        self.addEventListener('notificationclick', (event) => {
            console.log('Notification click received.', event);
            event.notification.close(); // 알림 닫기

            const clickData = event.notification.data; // 페이로드의 data 필드 접근

            let targetUrl = 'https://bloomingswim.designusplus.com'; // 기본 이동 URL

            // 백엔드에서 보낸 data 페이로드에 'url' 필드가 있다면 해당 URL을 사용
            if (clickData && clickData.url) {
                targetUrl = clickData.url;
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