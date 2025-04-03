from app import create_app, db
from app.models import FitnessCategory, Mapping
from app.services import const, util
from app.services.emag_full_seq import fetch_all_fitness1_products


def populate_fitness_categories():
    for cat in const.FITNESS_CATEGORIES:
        # Check if the category already exists
        if not FitnessCategory.query.filter_by(name=cat).first():
            new_cat = FitnessCategory(name=cat)
            db.session.add(new_cat)
            print(f"Adding category: {cat}")
    db.session.commit()
    print("Categories populated successfully.")


def populate_mappings():
    fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    all_fitness1_categories = util.get_current_fitness1_categories(fitness1_products)
    # get a list of the fitness categories names
    emag_categories_names = [cat.name for cat in FitnessCategory.query.all()]

    # Step 6: Build a mapping between Fitness1 and EMAG categories
    categories_mapping = util.build_mapping(
        fitness1_categories=all_fitness1_categories,
        emag_categories=emag_categories_names,
        threshold=80,
        keywords_mapping=const.KEYWORDS_MAPPING,
    )
    mapped_categories_strings = util.map_fitness1_category_to_emag_category_string(
        categories_mapping
    )
    for f1_cat, emag_cat in mapped_categories_strings.items():
        # Check if the mapping already exists
        if (
            not Mapping.query.filter_by(fitness1_category=f1_cat)
            .filter_by(emag_category=emag_cat)
            .first()
        ):
            new_mapping = Mapping(fitness1_category=f1_cat, emag_category=emag_cat)
            db.session.add(new_mapping)
            print(f"Adding mapping: {f1_cat} -> {emag_cat}")
    db.session.commit()
    print("Mappings populated successfully.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        populate_fitness_categories()
        populate_mappings()
