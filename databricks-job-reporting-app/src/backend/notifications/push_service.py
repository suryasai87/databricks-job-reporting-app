"""
Mobile Push Notification Service for Databricks Jobs Monitor.

Provides push notification capabilities for iOS, Android, and Web browsers using:
- Firebase Cloud Messaging (FCM) for iOS and Android devices
- Web Push for browser notifications

Device tokens are stored in jobs_monitor.config.device_tokens table.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

logger = logging.getLogger(__name__)

# Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("firebase-admin not available - FCM push notifications disabled")

# Web Push
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    logger.warning("pywebpush not available - Web Push notifications disabled")


class DevicePlatform(Enum):
    """Supported device platforms."""
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert routing channels."""
    PUSH = "push"
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    ALL = "all"


@dataclass
class DeviceToken:
    """Represents a registered device for push notifications."""
    user_id: str
    device_token: str
    platform: DevicePlatform
    device_name: Optional[str] = None
    device_model: Optional[str] = None
    app_version: Optional[str] = None
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    # Web push specific fields
    endpoint: Optional[str] = None
    p256dh_key: Optional[str] = None
    auth_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "user_id": self.user_id,
            "device_token": self.device_token,
            "platform": self.platform.value,
            "device_name": self.device_name,
            "device_model": self.device_model,
            "app_version": self.app_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
            "endpoint": self.endpoint,
            "p256dh_key": self.p256dh_key,
            "auth_key": self.auth_key,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceToken":
        """Create from dictionary (database row)."""
        return cls(
            user_id=data["user_id"],
            device_token=data["device_token"],
            platform=DevicePlatform(data["platform"]),
            device_name=data.get("device_name"),
            device_model=data.get("device_model"),
            app_version=data.get("app_version"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            last_used_at=datetime.fromisoformat(data["last_used_at"]) if data.get("last_used_at") else None,
            is_active=data.get("is_active", True),
            endpoint=data.get("endpoint"),
            p256dh_key=data.get("p256dh_key"),
            auth_key=data.get("auth_key"),
        )

    @property
    def token_hash(self) -> str:
        """Get SHA256 hash of token for logging (avoid logging actual tokens)."""
        return hashlib.sha256(self.device_token.encode()).hexdigest()[:12]


@dataclass
class NotificationPayload:
    """Notification content and configuration."""
    title: str
    body: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    # Optional fields
    subtitle: Optional[str] = None
    image_url: Optional[str] = None
    click_action: Optional[str] = None
    deep_link: Optional[str] = None
    # Custom data payload
    data: Dict[str, str] = field(default_factory=dict)
    # iOS specific
    badge_count: Optional[int] = None
    sound: str = "default"
    # Android specific
    channel_id: str = "jobs_monitor_alerts"
    icon: str = "ic_notification"
    color: str = "#1565C0"
    # Notification grouping
    group_key: Optional[str] = None
    collapse_key: Optional[str] = None
    # TTL in seconds (default 1 hour)
    ttl: int = 3600

    def to_fcm_message(self, token: str) -> "messaging.Message":
        """Convert to FCM Message object."""
        if not FIREBASE_AVAILABLE:
            raise RuntimeError("Firebase Admin SDK not available")

        # Build notification
        notification = messaging.Notification(
            title=self.title,
            body=self.body,
            image=self.image_url,
        )

        # iOS-specific configuration
        apns = messaging.APNSConfig(
            headers={
                "apns-priority": "10" if self.priority in [NotificationPriority.HIGH, NotificationPriority.CRITICAL] else "5",
                "apns-expiration": str(int(datetime.now(timezone.utc).timestamp()) + self.ttl),
            },
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    alert=messaging.ApsAlert(
                        title=self.title,
                        subtitle=self.subtitle,
                        body=self.body,
                    ),
                    badge=self.badge_count,
                    sound=self.sound,
                    category=self.data.get("category", "JOB_ALERT"),
                    thread_id=self.group_key,
                ),
            ),
        )

        # Android-specific configuration
        android = messaging.AndroidConfig(
            priority="high" if self.priority in [NotificationPriority.HIGH, NotificationPriority.CRITICAL] else "normal",
            ttl=self.ttl,
            collapse_key=self.collapse_key,
            notification=messaging.AndroidNotification(
                title=self.title,
                body=self.body,
                icon=self.icon,
                color=self.color,
                sound=self.sound,
                channel_id=self.channel_id,
                click_action=self.click_action,
                image=self.image_url,
                tag=self.group_key,
            ),
        )

        # Web Push configuration
        webpush_config = messaging.WebpushConfig(
            headers={
                "TTL": str(self.ttl),
                "Urgency": "high" if self.priority in [NotificationPriority.HIGH, NotificationPriority.CRITICAL] else "normal",
            },
            notification=messaging.WebpushNotification(
                title=self.title,
                body=self.body,
                icon=self.icon,
                image=self.image_url,
                tag=self.group_key,
                renotify=True if self.group_key else False,
            ),
            fcm_options=messaging.WebpushFCMOptions(
                link=self.deep_link,
            ),
        )

        return messaging.Message(
            notification=notification,
            data=self.data,
            token=token,
            apns=apns,
            android=android,
            webpush=webpush_config,
        )

    def to_web_push_payload(self) -> Dict[str, Any]:
        """Convert to Web Push payload."""
        return {
            "title": self.title,
            "body": self.body,
            "icon": self.icon,
            "image": self.image_url,
            "badge": "/badge.png",
            "tag": self.group_key,
            "data": {
                **self.data,
                "deep_link": self.deep_link,
                "click_action": self.click_action,
            },
            "requireInteraction": self.priority in [NotificationPriority.HIGH, NotificationPriority.CRITICAL],
        }


@dataclass
class NotificationResult:
    """Result of a notification send attempt."""
    success: bool
    device_token: str
    platform: DevicePlatform
    message_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    should_unregister: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "device_token_hash": hashlib.sha256(self.device_token.encode()).hexdigest()[:12],
            "platform": self.platform.value,
            "message_id": self.message_id,
            "error": self.error,
            "error_code": self.error_code,
            "should_unregister": self.should_unregister,
            "timestamp": self.timestamp.isoformat(),
        }


class PushNotificationService:
    """
    Push notification service for iOS, Android, and Web platforms.

    Uses Firebase Cloud Messaging for iOS/Android and native Web Push for browsers.
    Device tokens are stored in jobs_monitor.config.device_tokens table.
    """

    # Table for device token storage
    DEVICE_TOKENS_TABLE = "jobs_monitor.config.device_tokens"

    # Error codes that indicate token should be unregistered
    UNREGISTERABLE_ERRORS = {
        "messaging/invalid-registration-token",
        "messaging/registration-token-not-registered",
        "messaging/invalid-argument",
        "NotRegistered",
        "InvalidRegistration",
    }

    def __init__(self, data_layer=None, max_workers: int = 10):
        """
        Initialize push notification service.

        Args:
            data_layer: Data access layer instance (optional, will use singleton if not provided)
            max_workers: Maximum concurrent notification sends
        """
        self._data_layer = data_layer
        self._max_workers = max_workers
        self._firebase_initialized = False
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        # Web Push configuration
        self._vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY")
        self._vapid_claims = {
            "sub": os.environ.get("VAPID_SUBJECT", "mailto:admin@databricks.com")
        }

        # Initialize Firebase
        self._init_firebase()

    @property
    def data_layer(self):
        """Get data layer, importing lazily to avoid circular imports."""
        if self._data_layer is None:
            from data.data_layer import get_data_layer
            self._data_layer = get_data_layer()
        return self._data_layer

    def _init_firebase(self):
        """Initialize Firebase Admin SDK."""
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase Admin SDK not installed")
            return

        if firebase_admin._apps:
            # Already initialized
            self._firebase_initialized = True
            return

        credentials_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
        if not credentials_path:
            logger.warning("FIREBASE_CREDENTIALS_PATH not set - FCM disabled")
            return

        try:
            cred = credentials.Certificate(credentials_path)
            firebase_admin.initialize_app(cred)
            self._firebase_initialized = True
            logger.info("Firebase Admin SDK initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")

    def register_device(
        self,
        user_id: str,
        device_token: str,
        platform: str,
        device_name: Optional[str] = None,
        device_model: Optional[str] = None,
        app_version: Optional[str] = None,
        # Web push specific
        endpoint: Optional[str] = None,
        p256dh_key: Optional[str] = None,
        auth_key: Optional[str] = None,
    ) -> DeviceToken:
        """
        Register a device for push notifications.

        Args:
            user_id: User identifier
            device_token: FCM token or Web Push subscription
            platform: Device platform (ios, android, web)
            device_name: Optional device name
            device_model: Optional device model
            app_version: Optional app version
            endpoint: Web Push endpoint URL
            p256dh_key: Web Push p256dh key
            auth_key: Web Push auth key

        Returns:
            DeviceToken object
        """
        platform_enum = DevicePlatform(platform.lower())
        now = datetime.now(timezone.utc)

        device = DeviceToken(
            user_id=user_id,
            device_token=device_token,
            platform=platform_enum,
            device_name=device_name,
            device_model=device_model,
            app_version=app_version,
            created_at=now,
            last_used_at=now,
            is_active=True,
            endpoint=endpoint,
            p256dh_key=p256dh_key,
            auth_key=auth_key,
        )

        # Upsert device token in database
        self._upsert_device_token(device)

        logger.info(f"Device registered: user={user_id}, platform={platform}, token_hash={device.token_hash}")
        return device

    def unregister_device(self, user_id: str, device_token: str) -> bool:
        """
        Unregister a device from push notifications.

        Args:
            user_id: User identifier
            device_token: Device token to unregister

        Returns:
            True if device was unregistered
        """
        try:
            sql = f"""
                UPDATE {self.DEVICE_TOKENS_TABLE}
                SET is_active = false,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %(user_id)s
                  AND device_token = %(device_token)s
            """
            self.data_layer.query(sql, {
                "user_id": user_id,
                "device_token": device_token,
            }, force_warehouse=True)

            token_hash = hashlib.sha256(device_token.encode()).hexdigest()[:12]
            logger.info(f"Device unregistered: user={user_id}, token_hash={token_hash}")
            return True
        except Exception as e:
            logger.error(f"Failed to unregister device: {e}")
            return False

    def get_user_devices(self, user_id: str, active_only: bool = True) -> List[DeviceToken]:
        """
        Get all registered devices for a user.

        Args:
            user_id: User identifier
            active_only: Only return active devices

        Returns:
            List of DeviceToken objects
        """
        try:
            sql = f"""
                SELECT user_id, device_token, platform, device_name, device_model,
                       app_version, created_at, last_used_at, is_active,
                       endpoint, p256dh_key, auth_key
                FROM {self.DEVICE_TOKENS_TABLE}
                WHERE user_id = %(user_id)s
            """
            if active_only:
                sql += " AND is_active = true"

            rows = self.data_layer.query(sql, {"user_id": user_id})
            return [DeviceToken.from_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get user devices: {e}")
            return []

    def send_notification(
        self,
        user_id: str,
        payload: NotificationPayload,
    ) -> List[NotificationResult]:
        """
        Send notification to all devices for a user.

        Args:
            user_id: User identifier
            payload: Notification payload

        Returns:
            List of NotificationResult for each device
        """
        devices = self.get_user_devices(user_id)
        if not devices:
            logger.info(f"No devices registered for user: {user_id}")
            return []

        results = []
        futures = []

        for device in devices:
            future = self._executor.submit(self._send_to_device, device, payload)
            futures.append((device, future))

        for device, future in futures:
            try:
                result = future.result(timeout=30)
                results.append(result)

                # Handle unregistered tokens
                if result.should_unregister:
                    self.unregister_device(device.user_id, device.device_token)
            except Exception as e:
                results.append(NotificationResult(
                    success=False,
                    device_token=device.device_token,
                    platform=device.platform,
                    error=str(e),
                ))

        # Update last_used_at for successful sends
        self._update_last_used(user_id, [r for r in results if r.success])

        return results

    def send_bulk_notifications(
        self,
        user_ids: List[str],
        payload: NotificationPayload,
    ) -> Dict[str, List[NotificationResult]]:
        """
        Send notification to multiple users.

        Args:
            user_ids: List of user identifiers
            payload: Notification payload

        Returns:
            Dictionary mapping user_id to list of NotificationResult
        """
        results = {}
        futures = []

        for user_id in user_ids:
            future = self._executor.submit(self.send_notification, user_id, payload)
            futures.append((user_id, future))

        for user_id, future in futures:
            try:
                results[user_id] = future.result(timeout=60)
            except Exception as e:
                logger.error(f"Bulk notification failed for user {user_id}: {e}")
                results[user_id] = []

        total_sent = sum(len(r) for r in results.values())
        total_success = sum(sum(1 for n in r if n.success) for r in results.values())
        logger.info(f"Bulk notification complete: {total_success}/{total_sent} successful")

        return results

    def send_job_failure_alert(
        self,
        job_id: str,
        job_name: str,
        run_id: str,
        error_message: str,
        owner_email: Optional[str] = None,
        workspace_url: Optional[str] = None,
    ) -> List[NotificationResult]:
        """
        Send job failure alert to job owner.

        Args:
            job_id: Job identifier
            job_name: Job name
            run_id: Run identifier
            error_message: Error message
            owner_email: Job owner email (user_id)
            workspace_url: Databricks workspace URL

        Returns:
            List of NotificationResult
        """
        if not owner_email:
            logger.warning(f"No owner email for job {job_id}, cannot send alert")
            return []

        # Truncate error message if too long
        max_error_len = 200
        if len(error_message) > max_error_len:
            error_message = error_message[:max_error_len] + "..."

        # Build deep link to job run
        deep_link = None
        if workspace_url:
            deep_link = f"{workspace_url}/#job/{job_id}/run/{run_id}"

        payload = NotificationPayload(
            title=f"Job Failed: {job_name}",
            body=error_message,
            priority=NotificationPriority.HIGH,
            deep_link=deep_link,
            click_action="OPEN_JOB_RUN",
            data={
                "type": "job_failure",
                "job_id": str(job_id),
                "job_name": job_name,
                "run_id": str(run_id),
            },
            group_key=f"job_failures_{job_id}",
            collapse_key=f"job_{job_id}",
            channel_id="job_failures",
            color="#D32F2F",  # Red color for failures
            sound="alert",
            badge_count=1,
        )

        return self.send_notification(owner_email, payload)

    def _send_to_device(
        self,
        device: DeviceToken,
        payload: NotificationPayload,
    ) -> NotificationResult:
        """Send notification to a single device."""
        try:
            if device.platform == DevicePlatform.WEB and device.endpoint:
                return self._send_web_push(device, payload)
            else:
                return self._send_fcm(device, payload)
        except Exception as e:
            return NotificationResult(
                success=False,
                device_token=device.device_token,
                platform=device.platform,
                error=str(e),
            )

    def _send_fcm(
        self,
        device: DeviceToken,
        payload: NotificationPayload,
    ) -> NotificationResult:
        """Send notification via Firebase Cloud Messaging."""
        if not self._firebase_initialized:
            return NotificationResult(
                success=False,
                device_token=device.device_token,
                platform=device.platform,
                error="Firebase not initialized",
            )

        try:
            message = payload.to_fcm_message(device.device_token)
            response = messaging.send(message)

            return NotificationResult(
                success=True,
                device_token=device.device_token,
                platform=device.platform,
                message_id=response,
            )
        except messaging.UnregisteredError:
            return NotificationResult(
                success=False,
                device_token=device.device_token,
                platform=device.platform,
                error="Device token unregistered",
                error_code="messaging/registration-token-not-registered",
                should_unregister=True,
            )
        except messaging.SenderIdMismatchError:
            return NotificationResult(
                success=False,
                device_token=device.device_token,
                platform=device.platform,
                error="Sender ID mismatch",
                error_code="messaging/sender-id-mismatch",
                should_unregister=True,
            )
        except Exception as e:
            error_str = str(e)
            should_unregister = any(code in error_str for code in self.UNREGISTERABLE_ERRORS)

            return NotificationResult(
                success=False,
                device_token=device.device_token,
                platform=device.platform,
                error=error_str,
                should_unregister=should_unregister,
            )

    def _send_web_push(
        self,
        device: DeviceToken,
        payload: NotificationPayload,
    ) -> NotificationResult:
        """Send notification via Web Push."""
        if not WEBPUSH_AVAILABLE:
            return NotificationResult(
                success=False,
                device_token=device.device_token,
                platform=device.platform,
                error="Web Push not available",
            )

        if not device.endpoint or not device.p256dh_key or not device.auth_key:
            return NotificationResult(
                success=False,
                device_token=device.device_token,
                platform=device.platform,
                error="Missing Web Push subscription details",
            )

        if not self._vapid_private_key:
            return NotificationResult(
                success=False,
                device_token=device.device_token,
                platform=device.platform,
                error="VAPID private key not configured",
            )

        try:
            subscription_info = {
                "endpoint": device.endpoint,
                "keys": {
                    "p256dh": device.p256dh_key,
                    "auth": device.auth_key,
                },
            }

            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload.to_web_push_payload()),
                vapid_private_key=self._vapid_private_key,
                vapid_claims=self._vapid_claims,
                ttl=payload.ttl,
            )

            return NotificationResult(
                success=True,
                device_token=device.device_token,
                platform=device.platform,
                message_id=f"webpush_{datetime.now(timezone.utc).timestamp()}",
            )
        except WebPushException as e:
            should_unregister = e.response and e.response.status_code in [404, 410]

            return NotificationResult(
                success=False,
                device_token=device.device_token,
                platform=device.platform,
                error=str(e),
                error_code=str(e.response.status_code) if e.response else None,
                should_unregister=should_unregister,
            )
        except Exception as e:
            return NotificationResult(
                success=False,
                device_token=device.device_token,
                platform=device.platform,
                error=str(e),
            )

    def _upsert_device_token(self, device: DeviceToken):
        """Insert or update device token in database."""
        try:
            # Use MERGE/UPSERT pattern
            sql = f"""
                MERGE INTO {self.DEVICE_TOKENS_TABLE} AS target
                USING (SELECT
                    %(user_id)s AS user_id,
                    %(device_token)s AS device_token,
                    %(platform)s AS platform,
                    %(device_name)s AS device_name,
                    %(device_model)s AS device_model,
                    %(app_version)s AS app_version,
                    %(endpoint)s AS endpoint,
                    %(p256dh_key)s AS p256dh_key,
                    %(auth_key)s AS auth_key
                ) AS source
                ON target.device_token = source.device_token
                WHEN MATCHED THEN
                    UPDATE SET
                        user_id = source.user_id,
                        platform = source.platform,
                        device_name = source.device_name,
                        device_model = source.device_model,
                        app_version = source.app_version,
                        endpoint = source.endpoint,
                        p256dh_key = source.p256dh_key,
                        auth_key = source.auth_key,
                        is_active = true,
                        last_used_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                WHEN NOT MATCHED THEN
                    INSERT (user_id, device_token, platform, device_name, device_model,
                            app_version, endpoint, p256dh_key, auth_key, is_active,
                            created_at, last_used_at, updated_at)
                    VALUES (source.user_id, source.device_token, source.platform,
                            source.device_name, source.device_model, source.app_version,
                            source.endpoint, source.p256dh_key, source.auth_key, true,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
            self.data_layer.query(sql, device.to_dict(), force_warehouse=True)
        except Exception as e:
            logger.error(f"Failed to upsert device token: {e}")
            raise

    def _update_last_used(self, user_id: str, successful_results: List[NotificationResult]):
        """Update last_used_at for devices that received notification."""
        if not successful_results:
            return

        try:
            tokens = [r.device_token for r in successful_results]
            placeholders = ", ".join([f"'{t}'" for t in tokens])

            sql = f"""
                UPDATE {self.DEVICE_TOKENS_TABLE}
                SET last_used_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %(user_id)s
                  AND device_token IN ({placeholders})
            """
            self.data_layer.query(sql, {"user_id": user_id}, force_warehouse=True)
        except Exception as e:
            logger.warning(f"Failed to update last_used_at: {e}")

    def cleanup_inactive_devices(self, days_inactive: int = 90) -> int:
        """
        Remove devices that haven't been used in specified days.

        Args:
            days_inactive: Number of days of inactivity before removal

        Returns:
            Number of devices removed
        """
        try:
            sql = f"""
                DELETE FROM {self.DEVICE_TOKENS_TABLE}
                WHERE last_used_at < CURRENT_TIMESTAMP - INTERVAL {days_inactive} DAY
                   OR is_active = false
            """
            self.data_layer.query(sql, force_warehouse=True)
            logger.info(f"Cleaned up inactive devices older than {days_inactive} days")
            return 0  # Delta Lake doesn't return affected rows easily
        except Exception as e:
            logger.error(f"Failed to cleanup inactive devices: {e}")
            return 0


class AlertRouter:
    """
    Routes alerts to appropriate notification channels based on configuration.

    Supports routing to: Push, Email, Slack, Webhooks
    """

    def __init__(
        self,
        push_service: Optional[PushNotificationService] = None,
        data_layer=None,
    ):
        """
        Initialize alert router.

        Args:
            push_service: Push notification service instance
            data_layer: Data access layer instance
        """
        self._push_service = push_service
        self._data_layer = data_layer

    @property
    def push_service(self) -> PushNotificationService:
        """Get push service, creating if needed."""
        if self._push_service is None:
            self._push_service = get_push_service()
        return self._push_service

    @property
    def data_layer(self):
        """Get data layer."""
        if self._data_layer is None:
            from data.data_layer import get_data_layer
            self._data_layer = get_data_layer()
        return self._data_layer

    def route_job_failure(
        self,
        job_id: str,
        job_name: str,
        run_id: str,
        error_message: str,
        owner_email: str,
        channels: Optional[Set[AlertChannel]] = None,
        workspace_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Route job failure alert to configured channels.

        Args:
            job_id: Job identifier
            job_name: Job name
            run_id: Run identifier
            error_message: Error message
            owner_email: Job owner email
            channels: Set of channels to route to (default: ALL)
            workspace_url: Databricks workspace URL

        Returns:
            Dictionary with results for each channel
        """
        if channels is None:
            channels = {AlertChannel.PUSH}

        results = {
            "job_id": job_id,
            "run_id": run_id,
            "channels": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Route to push notifications
        if AlertChannel.PUSH in channels or AlertChannel.ALL in channels:
            try:
                push_results = self.push_service.send_job_failure_alert(
                    job_id=job_id,
                    job_name=job_name,
                    run_id=run_id,
                    error_message=error_message,
                    owner_email=owner_email,
                    workspace_url=workspace_url,
                )
                results["channels"]["push"] = {
                    "success": any(r.success for r in push_results),
                    "devices_notified": sum(1 for r in push_results if r.success),
                    "total_devices": len(push_results),
                }
            except Exception as e:
                results["channels"]["push"] = {
                    "success": False,
                    "error": str(e),
                }

        # Route to email (placeholder - would integrate with email service)
        if AlertChannel.EMAIL in channels or AlertChannel.ALL in channels:
            results["channels"]["email"] = {
                "success": False,
                "error": "Email routing not implemented",
            }

        # Route to Slack (placeholder - would integrate with Slack webhook)
        if AlertChannel.SLACK in channels or AlertChannel.ALL in channels:
            results["channels"]["slack"] = {
                "success": False,
                "error": "Slack routing not implemented",
            }

        # Route to webhook (placeholder - would POST to configured webhook)
        if AlertChannel.WEBHOOK in channels or AlertChannel.ALL in channels:
            results["channels"]["webhook"] = {
                "success": False,
                "error": "Webhook routing not implemented",
            }

        return results

    def route_alert(
        self,
        user_ids: List[str],
        payload: NotificationPayload,
        channels: Optional[Set[AlertChannel]] = None,
    ) -> Dict[str, Any]:
        """
        Route generic alert to specified users and channels.

        Args:
            user_ids: List of user identifiers
            payload: Notification payload
            channels: Set of channels to route to

        Returns:
            Dictionary with results
        """
        if channels is None:
            channels = {AlertChannel.PUSH}

        results = {
            "user_count": len(user_ids),
            "channels": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if AlertChannel.PUSH in channels or AlertChannel.ALL in channels:
            try:
                push_results = self.push_service.send_bulk_notifications(user_ids, payload)
                total_success = sum(
                    sum(1 for r in user_results if r.success)
                    for user_results in push_results.values()
                )
                total_sent = sum(len(r) for r in push_results.values())

                results["channels"]["push"] = {
                    "success": total_success > 0,
                    "notifications_sent": total_success,
                    "total_attempts": total_sent,
                    "users_reached": sum(1 for r in push_results.values() if any(n.success for n in r)),
                }
            except Exception as e:
                results["channels"]["push"] = {
                    "success": False,
                    "error": str(e),
                }

        return results

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get notification preferences for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with user preferences
        """
        try:
            sql = """
                SELECT user_id, channel, enabled, quiet_hours_start,
                       quiet_hours_end, alert_types, updated_at
                FROM jobs_monitor.config.notification_preferences
                WHERE user_id = %(user_id)s
            """
            rows = self.data_layer.query(sql, {"user_id": user_id})

            preferences = {
                "user_id": user_id,
                "channels": {},
            }

            for row in rows:
                preferences["channels"][row["channel"]] = {
                    "enabled": row.get("enabled", True),
                    "quiet_hours_start": row.get("quiet_hours_start"),
                    "quiet_hours_end": row.get("quiet_hours_end"),
                    "alert_types": row.get("alert_types", []),
                }

            return preferences
        except Exception as e:
            logger.warning(f"Failed to get user preferences: {e}")
            return {"user_id": user_id, "channels": {}}

    def should_send_alert(
        self,
        user_id: str,
        channel: AlertChannel,
        alert_type: str,
    ) -> bool:
        """
        Check if alert should be sent based on user preferences.

        Args:
            user_id: User identifier
            channel: Alert channel
            alert_type: Type of alert (e.g., 'job_failure', 'sla_warning')

        Returns:
            True if alert should be sent
        """
        preferences = self.get_user_preferences(user_id)
        channel_prefs = preferences.get("channels", {}).get(channel.value, {})

        # Check if channel is enabled
        if not channel_prefs.get("enabled", True):
            return False

        # Check quiet hours
        quiet_start = channel_prefs.get("quiet_hours_start")
        quiet_end = channel_prefs.get("quiet_hours_end")

        if quiet_start and quiet_end:
            now = datetime.now(timezone.utc).hour
            if quiet_start <= now < quiet_end:
                logger.info(f"Alert suppressed due to quiet hours for user {user_id}")
                return False

        # Check alert type filters
        allowed_types = channel_prefs.get("alert_types", [])
        if allowed_types and alert_type not in allowed_types:
            return False

        return True


# Singleton instance
_push_service: Optional[PushNotificationService] = None


def get_push_service() -> PushNotificationService:
    """Get or create singleton push notification service."""
    global _push_service
    if _push_service is None:
        _push_service = PushNotificationService()
    return _push_service


def reset_push_service():
    """Reset singleton push service (for testing)."""
    global _push_service
    _push_service = None
