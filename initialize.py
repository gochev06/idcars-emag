import time
import requests
from app import create_app, db
from app.models import FitnessCategory, Mapping
from app.services import const, util
from app.services.emag_full_seq import (
    fetch_all_categories_from_categories_list_emag,
    fetch_all_emag_products,
    fetch_all_fitness1_products,
)


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


def create_product_name(product: dict) -> str:
    """
    Constructs a name string from product dictionary.
    Only includes non-empty parts to avoid ambiguity.
    """
    parts = [
        product.get("brand_name", ""),
        product.get("product_name", "").replace("|", ""),
        product.get("option", ""),
        product.get("pack", ""),
    ]

    # Filter out empty or None values and strip whitespace
    parts = [part.strip() for part in parts if part and part.strip()]

    return ", ".join(parts)


def update_emag_fitness_products_names():
    # Step 1: Fetch all EMAG products
    print("Starting product update process...")

    # Step 1: Fetch all EMAG products.
    emag_products_result, emag_products_fetched = fetch_all_emag_products(
        api_url=util.build_url(const.EMAG_URL, "product_offer", "read"),
        headers=const.EMAG_HEADERS,
        pause=0,
    )
    if not emag_products_result:
        print("Failed to fetch EMAG products.")
        return {"emag_products_fetched": len(emag_products_fetched)}
    print(f"Fetched {len(emag_products_fetched)} EMAG products.")

    # Step 2: Fetch all Fitness1 products.
    fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    print(f"Fetched {len(fitness1_products)} Fitness1 products.")

    # Step 3: Build mapping between EMAG and Fitness1 products based on EAN.
    emag_p_to_f1_p_map = util.create_emag_p_to_f1_p_map(
        emag_products_fetched, fitness1_products
    )
    print(f"Built mapping for {len(emag_p_to_f1_p_map)} products.")
    updated_emag_product_data = []
    for emag_p_id, f1_p in emag_p_to_f1_p_map:
        # TODO: check for option and pack and then combinme
        # them into the name string
        name_str = create_product_name(f1_p)
        updated_emag_product_data.append(
            {
                "name": name_str,
                "id": emag_p_id,
                "sale_price": f1_p["regular_price"],
                "status": f1_p["available"],
                "vat_id": 6,
            }
        )
    print([emag_p["name"] for emag_p in updated_emag_product_data])

    # Step 5: Split the updated product data into batches.
    batched_updated_emag_product_data = util.split_list(updated_emag_product_data, 50)
    print(
        f"Split updated data into {len(batched_updated_emag_product_data)} batches (batch size: {50})."
    )

    # Step 6: Process each batch and post updates.
    failed_updates = []
    for i, batch in enumerate(batched_updated_emag_product_data):
        print(f"Posting batch {i+1} of {len(batched_updated_emag_product_data)}...")
        time.sleep(1)  # Pause between batches
        response = requests.post(
            url=util.build_url(const.EMAG_URL, "product_offer", "save"),
            json=batch,
            headers=const.EMAG_HEADERS,
        )
        if not response.ok:
            print(
                f"Request failed for batch {i+1} with status code {response.status_code}."
            )
        data = util.EmagResponse(response.json())
        if data.is_error:
            print(f"Batch {i+1} errors: {data.messages} {data.errors}")
            failed_updates.append(
                {
                    "batch": i + 1,
                    "emag_product_data": batch,
                    "messages": data.messages,
                    "errors": data.errors,
                }
            )

    successful_count = len(updated_emag_product_data) - len(failed_updates)
    print(
        f"Update process completed: {successful_count} successful updates, {len(failed_updates)} failed batches."
    )

    # Return a summary dictionary for API consumption.
    return {
        "emag_products_fetched": len(emag_products_fetched),
        "fitness1_products_fetched": len(fitness1_products),
        "updated_entries": len(updated_emag_product_data),
        "successful_updates": successful_count,
        "failed_updates": failed_updates,
    }

    # for mapping in mappings:
    #     emag_category_id = util.get_emag_category_id(mapping.emag_category)
    #     if emag_category_id:
    #         mapping.emag_category_id = emag_category_id
    #         db.session.add(mapping)
    #         print(
    #             f"Updating mapping: {mapping.fitness1_category} -> {mapping.emag_category}"
    #         )


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        update_emag_fitness_products_names()
        # populate_fitness_categories()
        # populate_mappings()
