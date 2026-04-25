"""
Database models for federated learning
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    LargeBinary,
    String,
    Text,
)
from app.core.database import Base


class FederatedParticipant(Base):
    """Federated learning participant model"""

    __tablename__ = "federated_participants"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    organization = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_seen = Column(DateTime, default=datetime.utcnow, index=True)
    total_contributions = Column(Integer, default=0)
    total_samples = Column(Integer, default=0)
    average_accuracy = Column(Float, default=0.0)
    meta_data = Column(JSON, nullable=True)


class FederatedRound(Base):
    """Federated learning round model"""

    __tablename__ = "federated_rounds"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)  # active, completed, failed
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    num_participants = Column(Integer, default=0)
    num_updates = Column(Integer, default=0)
    aggregation_method = Column(String(50), nullable=False)
    config = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)


class FederatedModel(Base):
    """Federated model update model"""

    __tablename__ = "federated_models"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(String(100), nullable=False, index=True)
    round_id = Column(String(100), nullable=True, index=True)
    model_weights = Column(LargeBinary, nullable=False)
    num_samples = Column(Integer, nullable=False)
    loss = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_aggregated = Column(Boolean, default=False, index=True)
    aggregated_at = Column(DateTime, nullable=True, index=True)
    meta_data = Column(JSON, nullable=True)


class FederatedGlobalModel(Base):
    """Global federated model model"""

    __tablename__ = "federated_global_models"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(100), unique=True, nullable=False, index=True)
    model_type = Column(String(50), nullable=False)
    model_weights = Column(LargeBinary, nullable=False)
    version = Column(Integer, default=1, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_active = Column(Boolean, default=True, index=True)
    metrics = Column(JSON, nullable=True)
    config = Column(JSON, nullable=True)


class FederatedEvaluation(Base):
    """Federated model evaluation model"""

    __tablename__ = "federated_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(100), nullable=False, index=True)
    round_id = Column(String(100), nullable=True, index=True)
    evaluation_type = Column(String(50), nullable=False)  # global, local, test
    accuracy = Column(Float, nullable=False)
    precision = Column(Float, nullable=False)
    recall = Column(Float, nullable=False)
    f1_score = Column(Float, nullable=False)
    num_samples = Column(Integer, nullable=False)
    evaluated_at = Column(DateTime, default=datetime.utcnow, index=True)
    participant_id = Column(String(100), nullable=True, index=True)
    meta_data = Column(JSON, nullable=True)


class FederatedPrivacyLog(Base):
    """Federated learning privacy log model"""

    __tablename__ = "federated_privacy_logs"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(String(100), nullable=False, index=True)
    round_id = Column(String(100), nullable=True, index=True)
    privacy_budget = Column(Float, nullable=False)
    epsilon = Column(Float, nullable=False)
    delta = Column(Float, nullable=False)
    noise_added = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    action = Column(String(50), nullable=False)  # aggregation, update, evaluation
    meta_data = Column(JSON, nullable=True)


class FederatedCommunicationLog(Base):
    """Federated learning communication log model"""

    __tablename__ = "federated_communication_logs"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(String(100), nullable=False, index=True)
    round_id = Column(String(100), nullable=True, index=True)
    action = Column(String(50), nullable=False)  # submit, receive, aggregate
    data_size = Column(Integer, nullable=False)
    encryption_used = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    meta_data = Column(JSON, nullable=True)
