from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.db import Base
from app.main import migrate_database
from app.models import AnalysisResult, AuditEvent, Document, ReviewAnnotation, User


def test_initial_migration_creates_all_tables(tmp_path):
    engine=create_engine(f"sqlite:///{(tmp_path/'fresh.sqlite').as_posix()}")
    try:
        migrate_database(engine)
        tables=set(inspect(engine).get_table_names())
        assert set(Base.metadata.tables).issubset(tables)
        assert "alembic_version" in tables
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()=="0001_initial"
            assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
    finally:
        engine.dispose()


def test_initial_migration_downgrades_only_on_empty_disposable_database(tmp_path):
    engine=create_engine(f"sqlite:///{(tmp_path/'downgrade.sqlite').as_posix()}")
    try:
        migrate_database(engine)
        migration_dir=Path(__file__).resolve().parents[1]
        config=Config(str(migration_dir/"alembic.ini"))
        config.set_main_option("script_location",str(migration_dir/"migrations"))
        with engine.connect() as connection:
            config.attributes["connection"]=connection
            with connection.begin():
                command.downgrade(config,"base")
        assert not set(Base.metadata.tables).intersection(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_existing_schema_is_baselined_without_losing_user_data(tmp_path):
    engine=create_engine(f"sqlite:///{(tmp_path/'legacy.sqlite').as_posix()}")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            user=User(username="synthetic",password_hash="synthetic-hash")
            document=Document(owner_id=1,original_filename="synthetic.pdf",object_key="synthetic.pdf",mime_type="application/pdf",file_size=10,document_type="laboratory",status="completed",page_count=1)
            document.analysis=AnalysisResult(schema_version="1.0",structured_data={"items":[{"id":"glucose","review_status":"corrected"}]},review_status="needs_review")
            session.add(user); session.flush()
            document.owner_id=user.id
            session.add(document); session.flush()
            document.analysis.reviews.append(ReviewAnnotation(item_id="glucose",original_value="Glucose 106",corrected_value="Glucose 106 mg/dL",reviewer_feedback="synthetic review"))
            session.add(AuditEvent(actor_id=user.id,action="reviewed",resource_id=str(document.id),metadata_json={"synthetic":True}))
            session.commit()
            ids=(user.id,document.id,document.analysis.id)
        migrate_database(engine)
        with Session(engine) as session:
            user=session.get(User,ids[0]); document=session.get(Document,ids[1]); analysis=session.get(AnalysisResult,ids[2])
            assert user.username=="synthetic"
            assert document.status=="completed" and document.analysis.review_status=="needs_review"
            assert analysis.schema_version=="1.0"
            assert analysis.structured_data["items"][0]["review_status"]=="corrected"
            assert [(r.item_id,r.corrected_value) for r in analysis.reviews]==[("glucose","Glucose 106 mg/dL")]
            assert session.query(AuditEvent).filter_by(resource_id=str(document.id)).one().metadata_json=={"synthetic":True}
            assert session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()=="0001_initial"
    finally:
        engine.dispose()
