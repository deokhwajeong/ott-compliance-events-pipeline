"""Real-time alerting system for high-risk events"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from enum import Enum
import os

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    """Alert delivery channels"""
    SLACK = "slack"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    LOG = "log"


class AlertingSystem:
    """Multi-channel alerting for compliance violations"""
    
    def __init__(self):
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.email_config = {
            "smtp_server": os.getenv("SMTP_SERVER", "localhost"),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "sender_email": os.getenv("ALERT_EMAIL", "alerts@compliance-pipeline.local"),
            "recipient_emails": os.getenv("ALERT_RECIPIENTS", "security@example.com").split(",")
        }
        self.twilio_config = {
            "account_sid": os.getenv("TWILIO_ACCOUNT_SID"),
            "auth_token": os.getenv("TWILIO_AUTH_TOKEN"),
            "from_number": os.getenv("TWILIO_FROM_NUMBER")
        }
        self.alert_history: List[Dict] = []
        self.max_history = 10000
    
    async def send_alert(
        self,
        title: str,
        severity: AlertSeverity,
        event: Dict[str, Any],
        flags: List[str],
        risk_score: float,
        channels: List[AlertChannel] = None
    ) -> Dict[str, bool]:
        """
        Send alert through multiple channels based on severity.
        """
        if channels is None:
            # Default channels based on severity
            channels = self._get_default_channels(severity)
        
        results = {}
        
        for channel in channels:
            try:
                if channel == AlertChannel.SLACK:
                    results[channel.value] = await self._send_slack_alert(
                        title, severity, event, flags, risk_score
                    )
                elif channel == AlertChannel.EMAIL:
                    results[channel.value] = await self._send_email_alert(
                        title, severity, event, flags, risk_score
                    )
                elif channel == AlertChannel.SMS:
                    results[channel.value] = await self._send_sms_alert(
                        title, severity, event, flags, risk_score
                    )
                elif channel == AlertChannel.LOG:
                    results[channel.value] = self._send_log_alert(
                        title, severity, event, flags, risk_score
                    )
                elif channel == AlertChannel.WEBHOOK:
                    results[channel.value] = await self._send_webhook_alert(
                        title, severity, event, flags, risk_score
                    )
            except Exception as e:
                logger.error(f"Failed to send {channel.value} alert: {e}")
                results[channel.value] = False
        
        # Store in history
        self._record_alert(title, severity, event, results)
        
        return results
    
    async def _send_slack_alert(
        self,
        title: str,
        severity: AlertSeverity,
        event: Dict,
        flags: List[str],
        risk_score: float
    ) -> bool:
        """Send alert to Slack"""
        if not self.slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False
        
        try:
            import slack_sdk
            
            # Color based on severity
            color_map = {
                AlertSeverity.LOW: "#36a64f",
                AlertSeverity.MEDIUM: "#ff9900",
                AlertSeverity.HIGH: "#ff6600",
                AlertSeverity.CRITICAL: "#cc0000"
            }
            
            message = {
                "attachments": [
                    {
                        "color": color_map.get(severity, "#666666"),
                        "title": f"⚠️ {title}",
                        "fields": [
                            {"title": "Severity", "value": severity.value.upper(), "short": True},
                            {"title": "Risk Score", "value": f"{risk_score:.1f}", "short": True},
                            {"title": "User ID", "value": event.get("user_id", "N/A"), "short": True},
                            {"title": "Event Type", "value": event.get("event_type", "N/A"), "short": True},
                            {"title": "Flags", "value": " | ".join(flags[:3]) if flags else "None", "short": False},
                            {"title": "Timestamp", "value": event.get("timestamp", "N/A"), "short": False},
                        ],
                        "footer": "OTT Compliance Pipeline"
                    }
                ]
            }
            
            import requests
            response = requests.post(
                self.slack_webhook_url,
                json=message,
                timeout=5
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Slack alert error: {e}")
            return False
    
    async def _send_email_alert(
        self,
        title: str,
        severity: AlertSeverity,
        event: Dict,
        flags: List[str],
        risk_score: float
    ) -> bool:
        """Send alert via email"""
        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Compose email
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{severity.upper()}] {title}"
            msg["From"] = self.email_config["sender_email"]
            msg["To"] = ", ".join(self.email_config["recipient_emails"])
            
            html = f"""
            <html>
                <body style="font-family: Arial, sans-serif;">
                    <h2 style="color: #cc0000;">{title}</h2>
                    <p><strong>Severity:</strong> <span style="color: #ff0000;">{severity.value.upper()}</span></p>
                    <p><strong>Risk Score:</strong> {risk_score:.1f}</p>
                    <p><strong>User ID:</strong> {event.get('user_id', 'N/A')}</p>
                    <p><strong>Event Type:</strong> {event.get('event_type', 'N/A')}</p>
                    <p><strong>Region:</strong> {event.get('region', 'N/A')}</p>
                    <p><strong>Timestamp:</strong> {event.get('timestamp', 'N/A')}</p>
                    <h3>Risk Flags:</h3>
                    <ul>
                        {"".join(f"<li>{flag}</li>" for flag in flags)}
                    </ul>
                    <hr>
                    <p><em>Auto-generated by OTT Compliance Pipeline</em></p>
                </body>
            </html>
            """
            
            msg.attach(MIMEText(html, "html"))
            
            # Send email
            async with aiosmtplib.SMTP(
                hostname=self.email_config["smtp_server"],
                port=self.email_config["smtp_port"]
            ) as smtp:
                await smtp.send_message(msg)
            
            logger.info(f"Email alert sent to {self.email_config['recipient_emails']}")
            return True
            
        except Exception as e:
            logger.error(f"Email alert error: {e}")
            return False
    
    async def _send_sms_alert(
        self,
        title: str,
        severity: AlertSeverity,
        event: Dict,
        flags: List[str],
        risk_score: float
    ) -> bool:
        """Send alert via SMS (Twilio)"""
        if not self.twilio_config.get("account_sid"):
            logger.warning("Twilio not configured")
            return False
        
        try:
            from twilio.rest import Client
            
            client = Client(
                self.twilio_config["account_sid"],
                self.twilio_config["auth_token"]
            )
            
            message_text = (
                f"SECURITY ALERT: {title}\n"
                f"Severity: {severity.value.upper()}\n"
                f"Risk: {risk_score:.1f}\n"
                f"User: {event.get('user_id', 'N/A')}\n"
                f"Flags: {', '.join(flags[:2])}"
            )
            
            # Send SMS only for CRITICAL severity
            if severity == AlertSeverity.CRITICAL:
                message = client.messages.create(
                    body=message_text,
                    from_=self.twilio_config["from_number"],
                    to=os.getenv("ALERT_PHONE_NUMBER", "")
                )
                logger.info(f"SMS alert sent: {message.sid}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"SMS alert error: {e}")
            return False
    
    def _send_log_alert(
        self,
        title: str,
        severity: AlertSeverity,
        event: Dict,
        flags: List[str],
        risk_score: float
    ) -> bool:
        """Log alert message"""
        log_level = {
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }.get(severity, logging.WARNING)
        
        log_message = (
            f"{title} | Severity: {severity.value} | Risk: {risk_score:.1f} | "
            f"User: {event.get('user_id')} | Flags: {', '.join(flags)}"
        )
        
        logger.log(log_level, log_message)
        return True
    
    async def _send_webhook_alert(
        self,
        title: str,
        severity: AlertSeverity,
        event: Dict,
        flags: List[str],
        risk_score: float
    ) -> bool:
        """Send alert to custom webhook"""
        webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        if not webhook_url:
            return False
        
        try:
            import aiohttp
            
            payload = {
                "title": title,
                "severity": severity.value,
                "risk_score": risk_score,
                "event": event,
                "flags": flags,
                "timestamp": str(__import__('datetime').datetime.utcnow())
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, timeout=5) as resp:
                    return resp.status == 200
                    
        except Exception as e:
            logger.error(f"Webhook alert error: {e}")
            return False
    
    def _get_default_channels(self, severity: AlertSeverity) -> List[AlertChannel]:
        """Get default alert channels based on severity"""
        channels = [AlertChannel.LOG]
        
        if severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
            channels.append(AlertChannel.SLACK)
        
        if severity == AlertSeverity.CRITICAL:
            channels.extend([AlertChannel.EMAIL, AlertChannel.SMS])
        
        return channels
    
    def _record_alert(
        self,
        title: str,
        severity: AlertSeverity,
        event: Dict,
        results: Dict
    ) -> None:
        """Record alert in history"""
        alert_record = {
            "title": title,
            "severity": severity.value,
            "user_id": event.get("user_id"),
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            "channels": results
        }
        
        self.alert_history.append(alert_record)
        
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]


# Global instance
alerting_system = AlertingSystem()
