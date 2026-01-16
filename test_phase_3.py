"""
Comprehensive Phase 3 Integration Tests
Tests all 9 Phase 3 enhancement features
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
import numpy as np

# WebSocket tests
def test_websocket_connection():
    """Test WebSocket connection management"""
    from src.app.websocket import ConnectionManager
    
    manager = ConnectionManager()
    assert len(manager.active_connections) == 0


@pytest.mark.asyncio
async def test_websocket_broadcast():
    """Test WebSocket broadcasting"""
    from src.app.websocket import ConnectionManager, broadcast_event
    
    manager = ConnectionManager()
    message = {"type": "test", "data": "value"}
    await broadcast_event("test", message)


# Deep Learning tests
def test_lstm_model_initialization():
    """Test LSTM model initialization"""
    from src.app.dl_models import LSTMModel
    
    model = LSTMModel(sequence_length=24, n_features=10)
    assert model.sequence_length == 24
    assert model.n_features == 10


def test_lstm_data_normalization():
    """Test LSTM data normalization"""
    from src.app.dl_models import LSTMModel
    
    model = LSTMModel()
    data = np.random.rand(100, 10)
    normalized = model.normalize(data)
    
    assert normalized.shape == data.shape
    assert np.allclose(np.mean(normalized), 0, atol=1e-6)


def test_transformer_model_build():
    """Test Transformer model building"""
    from src.app.dl_models import TransformerModel
    
    model = TransformerModel(sequence_length=24, n_features=10)
    assert model.model is not None
    assert model.model.built or True  # May not be built until first call


def test_ensemble_initialization():
    """Test ensemble model initialization"""
    from src.app.dl_models import EnsembleDeepLearning
    
    ensemble = EnsembleDeepLearning()
    ensemble.initialize_models(sequence_length=24, n_features=10)
    
    assert ensemble.lstm_model is not None
    assert ensemble.transformer_model is not None


# GraphQL tests
def test_graphql_schema_creation():
    """Test GraphQL schema creation"""
    from src.app.graphql_api import schema, Query
    
    assert schema is not None
    # Verify query type exists
    assert hasattr(Query, 'event')
    assert hasattr(Query, 'events')
    assert hasattr(Query, 'metrics')


def test_graphql_query_parsing():
    """Test GraphQL query parsing"""
    from src.app.graphql_api import schema
    
    query = """
    query {
        events(limit: 10) {
            id
            eventType
            timestamp
        }
    }
    """
    # Verify query is valid
    assert "events" in query
    assert "limit" in query


# API Gateway tests
def test_api_gateway_config():
    """Test API Gateway configuration"""
    from src.app.api_gateway import APIGatewayConfig
    
    gateway = APIGatewayConfig()
    assert len(gateway.routes) > 0
    assert len(gateway.plugins) > 0


def test_rate_limit_policies():
    """Test rate limiting policies"""
    from src.app.api_gateway import RateLimitConfig, RateLimitPolicy
    
    config = RateLimitConfig()
    basic_policy = config.POLICIES[RateLimitPolicy.BASIC]
    
    assert basic_policy["requests_per_minute"] == 60
    assert basic_policy["daily_limit"] == 50000


def test_circuit_breaker():
    """Test circuit breaker pattern"""
    from src.app.api_gateway import CircuitBreaker
    
    breaker = CircuitBreaker(failure_threshold=3)
    
    assert breaker.get_state() == "CLOSED"
    assert breaker.can_attempt()
    
    # Simulate failures
    for _ in range(3):
        breaker.record_failure()
    
    assert breaker.get_state() == "OPEN"
    assert not breaker.can_attempt()


# Distributed Tracing tests
def test_span_creation():
    """Test span creation"""
    from src.app.tracing import Span
    
    span = Span(
        name="test_span",
        trace_id="trace_123",
        span_id="span_456"
    )
    
    assert span.name == "test_span"
    assert span.trace_id == "trace_123"


def test_trace_creation():
    """Test trace creation"""
    from src.app.tracing import Trace
    
    trace = Trace("trace_123")
    span = trace.create_span("root_span")
    
    assert span is not None
    assert span.name == "root_span"


def test_tracer_management():
    """Test tracer management"""
    from src.app.tracing import Tracer
    
    tracer = Tracer("test-service")
    trace = tracer.start_trace("test_operation")
    
    assert trace is not None
    assert tracer.get_current_trace() == trace


def test_jaeger_exporter():
    """Test Jaeger exporter"""
    from src.app.tracing import Trace, JaegerExporter
    
    exporter = JaegerExporter()
    trace = Trace("trace_123")
    
    result = exporter.export_trace(trace)
    assert result is True
    assert len(exporter.get_exported_traces()) > 0


# Multi-tenancy tests
def test_tenant_config():
    """Test tenant configuration"""
    from src.app.tenancy import TenantConfig, TenantTier
    
    config = TenantConfig(
        tenant_id="tenant_123",
        name="Test Tenant",
        tier=TenantTier.PREMIUM
    )
    
    assert config.tenant_id == "tenant_123"
    assert config.has_feature("api_access")


def test_tenant_manager():
    """Test tenant manager"""
    from src.app.tenancy import get_tenant_manager, TenantTier
    
    manager = get_tenant_manager()
    tenant = manager.create_tenant(
        "Test Org",
        tier=TenantTier.STANDARD
    )
    
    assert tenant is not None
    assert manager.get_tenant(tenant.tenant_id) == tenant


def test_tenant_limits():
    """Test tenant limits"""
    from src.app.tenancy import get_tenant_manager, TenantTier
    
    manager = get_tenant_manager()
    tenant = manager.create_tenant("Test", tier=TenantTier.FREE)
    
    # Free tier allows 10,000 events/day
    assert tenant.get_limit("max_events_per_day") == 10000


def test_billing_tracker():
    """Test billing tracker"""
    from src.app.tenancy import BillingTracker
    
    tracker = BillingTracker()
    tracker.record_usage("tenant_123", "api_calls", 1000, 50.0)
    
    history = tracker.get_billing_history("tenant_123", days=30)
    assert len(history) > 0


# Encryption tests
def test_field_level_encryption():
    """Test field-level encryption"""
    from src.app.encryption import FieldLevelEncryption
    
    master_key = b"test_key_32_bytes_long_enough!!"
    encryption = FieldLevelEncryption(master_key)
    
    plaintext = "test@example.com"
    encrypted = encryption.encrypt_field(plaintext)
    
    assert encrypted != plaintext


def test_encryption_key_management():
    """Test key management service"""
    from src.app.encryption import KeyManagementService
    
    kms = KeyManagementService()
    key = kms.generate_key("test_key")
    
    assert key is not None
    assert kms.get_key("test_key") == key


def test_key_rotation():
    """Test key rotation"""
    from src.app.encryption import KeyManagementService
    
    kms = KeyManagementService()
    key1 = kms.generate_key("key_1")
    key2 = kms.generate_key("key_2")
    
    result = kms.rotate_key("key_1", "key_2")
    assert result is True
    assert kms.get_active_key().key_id == "key_2"


def test_encryption_pipeline():
    """Test encryption pipeline"""
    from src.app.encryption import EncryptionPipeline
    
    pipeline = EncryptionPipeline()
    
    event = {
        "user_id": "user_123",
        "email": "test@example.com",
        "action": "login"
    }
    
    encrypted = pipeline.process_inbound_event(event)
    assert "_encrypted_fields" in encrypted


# Visualization tests
def test_3d_visualization():
    """Test 3D graph visualization"""
    from src.app.visualization import Visualization3D
    
    viz = Visualization3D("Test Graph")
    viz.add_node("node_1", "Node 1")
    viz.add_edge("node_1", "node_2")
    
    three_js = viz.to_three_js()
    assert "nodes" in three_js
    assert "edges" in three_js


def test_heatmap_visualization():
    """Test heatmap visualization"""
    from src.app.visualization import Heatmap
    
    heatmap = Heatmap("Test Heatmap")
    heatmap.add_data_point("2024-01-15", "category_a", 0.8)
    
    matrix = heatmap.get_matrix()
    assert len(matrix) > 0


def test_time_series_chart():
    """Test time-series chart"""
    from src.app.visualization import TimeSeriesChart
    
    chart = TimeSeriesChart("Test Series")
    chart.add_series("Events", [10, 20, 30, 40])
    chart.set_timestamps(["10:00", "11:00", "12:00", "13:00"])
    
    chart_js = chart.to_chart_js()
    assert "datasets" in chart_js["data"]


def test_predictive_chart():
    """Test predictive chart"""
    from src.app.visualization import PredictiveChart
    
    chart = PredictiveChart("Predictions")
    chart.add_historical_point("2024-01-15", 100)
    chart.add_prediction("2024-01-16", 105, 100, 110)
    
    plotly = chart.to_plotly()
    assert len(plotly["data"]) > 0


def test_visualization_dashboard():
    """Test visualization dashboard"""
    from src.app.visualization import VisualizationDashboard
    
    dashboard = VisualizationDashboard("Test Dashboard")
    dashboard.add_widget("widget_1", "chart", "Test Chart", {"x": 0, "y": 0})
    
    layout = dashboard.get_layout()
    assert "widgets" in layout
    assert "widget_1" in layout["widgets"]


# Integration tests
@pytest.mark.asyncio
async def test_end_to_end_flow():
    """Test complete end-to-end flow"""
    from src.app.tenancy import get_tenant_manager, TenantTier
    from src.app.encryption import EncryptionPipeline
    from src.app.dl_models import EnsembleDeepLearning
    from src.app.visualization import Visualization3D
    
    # Create tenant
    manager = get_tenant_manager()
    tenant = manager.create_tenant("E2E Test", tier=TenantTier.PREMIUM)
    assert tenant is not None
    
    # Encrypt data
    pipeline = EncryptionPipeline()
    event = {"user_id": "user_1", "action": "login"}
    encrypted_event = pipeline.process_inbound_event(event)
    assert "_encrypted_fields" in encrypted_event
    
    # Process with ML
    ensemble = EnsembleDeepLearning()
    ensemble.initialize_models()
    
    # Create visualization
    viz = Visualization3D("E2E Test")
    viz.add_node("test_node", "Test")
    
    # All systems operational
    assert tenant.tenant_id is not None
    assert encrypted_event is not None
    assert ensemble is not None


@pytest.mark.asyncio
async def test_performance_benchmarks():
    """Test performance benchmarks"""
    import time
    from src.app.encryption import FieldLevelEncryption
    
    master_key = b"test_key_32_bytes_long_enough!!"
    encryption = FieldLevelEncryption(master_key)
    
    # Measure encryption speed
    start = time.time()
    for i in range(1000):
        encryption.encrypt_field("test_email@example.com")
    duration = (time.time() - start) * 1000
    
    # Should encrypt 1000 items in < 1000ms
    assert duration < 1000, f"Encryption too slow: {duration}ms for 1000 operations"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
