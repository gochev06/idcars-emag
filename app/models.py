from app import db
from datetime import datetime, timezone


class FitnessCategory(db.Model):
    __tablename__ = "fitness_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    emag_category_id = db.Column(db.Integer, nullable=True)
    emag_product_name_category = db.Column(db.String(255), nullable=True)

    def as_dict(self):
        return {"id": self.id, "name": self.name}


class Mapping(db.Model):
    __tablename__ = "mappings"
    id = db.Column(db.Integer, primary_key=True)
    fitness1_category = db.Column(db.String(255), nullable=False)
    # The EMAG category will be one of the allowed values from FitnessCategory.
    emag_category = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    def as_dict(self):
        return {
            "id": self.id,
            "fitness1_category": self.fitness1_category,
            "emag_category": self.emag_category,
            "emag_category_id": self.emag_category_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
