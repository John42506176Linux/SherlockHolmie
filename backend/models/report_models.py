from sqlalchemy import  Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column,declarative_base
import datetime
import logging.handlers

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

Base = declarative_base()

class PainPoint(Base):
    __tablename__ = 'pain_points'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    persona_id: Mapped[int] = mapped_column(Integer, ForeignKey('personas.id'), nullable=False)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey('reports.id'), nullable=False)

    persona: Mapped["Persona"] = relationship('Persona', back_populates='pain_points', cascade='all, delete-orphan')
    report: Mapped["Report"] = relationship('Report', back_populates='pain_points', cascade='all, delete-orphan')


class Persona(Base):
    __tablename__ = 'personas'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey('reports.id'), nullable=False)

    report: Mapped["Report"] = relationship('Report', back_populates='personas', cascade='all, delete-orphan')
    pain_points: Mapped[list["PainPoint"]] = relationship('PainPoint', back_populates='persona', cascade='all, delete-orphan')


class Report(Base):
    __tablename__ = 'reports'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    space: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=True)
    objective: Mapped[str] = mapped_column(String, nullable=True)
    perspective: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default='processing')

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.datetime.now(DateTime.timezone.utc))

    personas: Mapped[list["Persona"]] = relationship('Persona', back_populates='report', cascade='all, delete-orphan')
    insights: Mapped[list["Insight"]] = relationship('Insight', back_populates='report', cascade='all, delete-orphan')
    pain_points: Mapped[list["PainPoint"]] = relationship('PainPoint', back_populates='report', cascade='all, delete-orphan')


class Insight(Base):
    __tablename__ = 'insights'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(String, nullable=False)
    conclusion: Mapped[str] = mapped_column(String, nullable=False)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey('reports.id'), nullable=False)

    report: Mapped["Report"] = relationship('Report', back_populates='insights', cascade='all, delete-orphan')

    attitudinal_insights: Mapped[list["AttitudinalInsight"]] = relationship(
        'AttitudinalInsight', back_populates='insight_rel', cascade='all, delete-orphan'
    )
    behavioral_insights: Mapped[list["BehavioralInsight"]] = relationship(
        'BehavioralInsight', back_populates='insight_rel', cascade='all, delete-orphan'
    )
    user_segments: Mapped[list["UserSegment"]] = relationship(
        'UserSegment', back_populates='insight_rel', cascade='all, delete-orphan'
    )



class AttitudinalInsight(Base):
    __tablename__ = 'attitudinal_insights'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    insight: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    quote: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    insight_id: Mapped[int] = mapped_column(Integer, ForeignKey('insights.id'), nullable=False)

    insight_rel: Mapped["Insight"] = relationship('Insight', back_populates='attitudinal_insights')


class BehavioralInsight(Base):
    __tablename__ = 'behavioral_insights'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    insight: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    quote: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    insight_id: Mapped[int] = mapped_column(Integer, ForeignKey('insights.id'), nullable=False)

    insight_rel: Mapped["Insight"] = relationship('Insight', back_populates='behavioral_insights')


class UserSegment(Base):
    __tablename__ = 'user_segments'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    insight_id: Mapped[int] = mapped_column(Integer, ForeignKey('insights.id'), nullable=False)

    insight_rel: Mapped["Insight"] = relationship('Insight', back_populates='user_segments')