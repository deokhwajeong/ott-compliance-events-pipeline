# Compliance Reporting Guide

## Overview
Comprehensive guide for generating and exporting compliance reports.

## Report Types

### Executive Summary Report
- Key compliance metrics
- Violation trends
- Risk assessment overview
- Regulatory status

### Detailed Compliance Report
- Event-level analysis
- Violation breakdown by regulation
- User risk profiles
- Temporal patterns

### ML Performance Report
- Model accuracy metrics
- Feature importance rankings
- Prediction confidence analysis
- Anomaly detection statistics

## Report Generation

```python
from src.app.report_generator import ComplianceReporter

reporter = ComplianceReporter()

# Generate executive summary
summary = reporter.generate_executive_summary(
    date_range=('2026-01-01', '2026-01-16'),
    regions=['US', 'EU', 'ASIA']
)

# Export to formats
reporter.export_to_pdf(summary, 'compliance_report.pdf')
reporter.export_to_json(summary, 'compliance_report.json')
reporter.export_to_csv(summary, 'compliance_report.csv')
```

## Dashboard Integration

Reports are automatically updated in the Grafana dashboard:
- Real-time metric updates
- Interactive visualizations
- Custom date range selection
- Export capabilities

## Data Privacy

All reports maintain data privacy standards:
- PII redaction
- Aggregated metrics only
- User consent tracking
- Regional compliance adherence

## Schedule Reports

```python
from src.app.model_scheduler import ReportScheduler

scheduler = ReportScheduler()

# Daily compliance summary
scheduler.schedule_daily(
    report_type='executive_summary',
    recipients=['compliance@company.com'],
    time='09:00'
)

# Weekly detailed report
scheduler.schedule_weekly(
    report_type='detailed_compliance',
    recipients=['team@company.com'],
    day='monday',
    time='08:00'
)

# Monthly ML performance
scheduler.schedule_monthly(
    report_type='ml_performance',
    recipients=['data_science@company.com'],
    day=1,
    time='10:00'
)
```

## Best Practices

1. **Regular Review**: Schedule weekly reviews of compliance metrics
2. **Trend Analysis**: Compare month-over-month patterns
3. **Risk Assessment**: Prioritize violations by severity
4. **Action Items**: Document remediation steps
5. **Stakeholder Communication**: Share insights with relevant teams

## Metrics Explained

### Compliance Rate
Percentage of events meeting regulatory requirements.

### Violation Severity
- Critical (0): GDPR Article 6 violations
- High (1): Data retention breaches
- Medium (2): Consent tracking failures
- Low (3): Documentation gaps

### Risk Score
0-100 scale indicating user/region risk level:
- 0-25: Low risk
- 25-50: Medium risk
- 50-75: High risk
- 75-100: Critical risk

