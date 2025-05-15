import time
import requests
from app import create_app, db
from app.models import FitnessCategory, Mapping
from app.services import const, util
from app.services.emag_full_seq import (
    fetch_all_categories_from_categories_list_emag,
    create_emag_product_from_fields,
    fetch_all_emag_products,
    fetch_all_fitness1_products,
    post_emag_product,
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
        api_url=util.build_url(
            base_url=const.EMAG_URL, resource="product_offer", action="read"
        ),
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
            url=util.build_url(
                base_url=const.EMAG_URL, resource="product_offer", action="save"
            ),
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


def set_emag_categories_ids():
    # Step 1: Fetch all EMAG products
    emag_products_result, emag_products_fetched = fetch_all_emag_products(
        api_url=util.build_url(
            base_url=const.EMAG_URL, resource="product_offer", action="read"
        ),
        headers=const.EMAG_HEADERS,
    )
    if not emag_products_result:
        print("Failed to fetch EMAG products.")
        return {"emag_products_fetched": len(emag_products_fetched)}
    print(f"Fetched {len(emag_products_fetched)} EMAG products.")

    current_emag_categories = util.get_current_emag_products_categories(
        emag_products_fetched
    )
    all_emag_categories = fetch_all_categories_from_categories_list_emag(
        api_url=util.build_url(
            base_url=const.EMAG_URL, resource="category", action="read"
        ),
        headers=const.EMAG_HEADERS,
        categories_list=current_emag_categories,
    )
    all_fitness_emag_categories = util.get_fitness_related_emag_categories(
        all_emag_categories, const.FITNESS_CATEGORIES
    )
    cat_name_to_id_map = {cat["name"]: cat["id"] for cat in all_fitness_emag_categories}
    print(cat_name_to_id_map)

    # Step 2: Update the FitnessCategory table with EMAG category IDs
    for cat in FitnessCategory.query.all():
        emag_category_id = cat_name_to_id_map.get(cat.name)
        if emag_category_id:
            cat.emag_category_id = emag_category_id
            db.session.add(cat)
            print(f"Updating category: {cat.name} with ID: {emag_category_id}")
    db.session.commit()
    print("Categories IDs updated successfully.")


def create_romania_products():
    # Step 1: Fetch all EMAG products
    emag_products_result, emag_products_fetched = fetch_all_emag_products(
        api_url=util.build_url(
            base_url=const.EMAG_URL,
            url_ext="ro",
            resource="product_offer",
            action="read",
        ),
        headers=const.EMAG_HEADERS,
    )
    if not emag_products_result:
        print("Failed to fetch EMAG products.")
        return {"emag_products_fetched": len(emag_products_fetched)}
    print(f"Fetched {len(emag_products_fetched)} EMAG products.")

    # Step 2: Fetch all Fitness1 products
    fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    print(f"Fetched {len(fitness1_products)} Fitness1 products.")

    # Step 3: Determine related EMAG products based on matching EAN (barcode)
    fitness1_related_emag_products = (
        util.get_fitness1_related_emag_products_based_on_ean(
            emag_products_fetched, fitness1_products
        )
    )
    print(
        f"Fetched {len(fitness1_related_emag_products)} Fitness1 related EMAG products."
    )

    # Step 4: Get current EMAG categories from the remaining products
    current_emag_categories = util.get_current_emag_products_categories(
        emag_products_fetched
    )
    print(f"Fetched {len(current_emag_categories)} EMAG categories.")

    # Fetch detailed EMAG category data
    all_emag_categories = fetch_all_categories_from_categories_list_emag(
        api_url=util.build_url(
            base_url=const.EMAG_URL,
            url_ext="ro",
            resource="category",
            action="read",
        ),
        headers=const.EMAG_HEADERS,
        categories_list=current_emag_categories,
    )
    print(f"Fetched {len(all_emag_categories)} EMAG categories.")

    name_to_id = {cat.name: cat.emag_category_id for cat in FitnessCategory.query.all()}
    fitness1_to_emag_id = {
        mapping.fitness1_category: name_to_id.get(mapping.emag_category)
        for mapping in Mapping.query.all()
    }

    # Step 7: Filter Fitness1 products to include only those with a mapped EMAG category
    valid_fitness1_products_data = util.get_fitness1_products_with_mapped_categories(
        fitness1_products, fitness1_to_emag_id
    )
    valid_fitness1_products = [
        util.Fitness1Product.from_dict(product)
        for product in valid_fitness1_products_data
    ]

    # Step 8: Map each Fitness1 product to its corresponding EMAG category data
    # f1_to_emag_categories = util.map_fitness1_category_to_emag_category_data(
    #     mapped_categories_strings, all_fitness_emag_categories
    # )

    # # Get all existing EMAG product IDs (for generating a valid new ID if needed)
    all_emag_product_ids = [product["id"] for product in emag_products_fetched]

    # # Step 9: Create new EMAG products by merging data from Fitness1 with EMAG category info
    emag_products_created = []
    for fitness1_product in valid_fitness1_products:
        emag_product = util.create_emag_product_from_fitness1_product(fitness1_product)
        if emag_product.ean in [
            product["ean"][0] for product in fitness1_related_emag_products
        ]:
            # get the id of the found product and set it to the emag product
            emag_product.id = util.get_emag_product_id_by_ean(
                emag_product.ean, fitness1_related_emag_products
            )
            emag_product.part_number = util.get_emag_part_number_by_ean(
                emag_product.ean, fitness1_related_emag_products
            )
        else:
            emag_product.id = util.get_valid_emag_product_id(all_emag_product_ids)
        emag_product.category_id = fitness1_to_emag_id.get(
            fitness1_product.category, None
        )
        emag_product.part_number = f"IDCARS-{emag_product.id}"

        # Now, create the product name
        name_str = create_product_name(fitness1_product.to_dict())
        # initialize the translator
        from translate import Translator

        translator = Translator(from_lang="bg", to_lang="ro")
        emag_product.name = translator.translate(name_str)
        print(f"Translated name: {emag_product.name}")
        descr_chunks = util.split_text_by_sentences(emag_product.description)
        translated_chunks = [translator.translate(chunk) for chunk in descr_chunks]
        emag_product.description = " ".join(translated_chunks)
        print(f"Translated description: {emag_product.description}")
        # Convert the price  from bgn to ron
        from currency_converter import CurrencyConverter

        c = CurrencyConverter()
        emag_product.sale_price = round(
            c.convert(emag_product.sale_price, "BGN", "RON"), 2
        )
        print(
            f"Converted price: {emag_product.sale_price} RON (from {fitness1_product.regular_price} BGN)"
        )

        emag_products_created.append(emag_product)

    print(f"Created {len(emag_products_created)} EMAG product objects.")
    print("example product:", emag_products_created[0])
    print("Example product data:", emag_products_created[0].to_dict())

    # # Step 10: Post the created EMAG products in batches
    # # Note: The post_emag_product function should already handle splitting into batches.
    products_data = [product.to_dict() for product in emag_products_created]
    failed_products = post_emag_product(
        emag_product_data=products_data,
        api_url=util.build_url(
            base_url=const.EMAG_URL,
            url_ext="ro",
            resource="product_offer",
            action="save",
        ),
        headers=const.EMAG_HEADERS,
        batch_size=50,
    )

    successful_count = len(emag_products_created) - len(failed_products)
    print(
        f"Successfully posted {successful_count} EMAG products, {len(failed_products)} failed."
    )

    # # Instead of writing to a file, return a summary dictionary
    return {
        "emag_products_fetched": len(emag_products_fetched),
        "fitness1_products_fetched": len(fitness1_products),
        "emag_categories_fetched": len(all_emag_categories),
        "emag_products_created": len(emag_products_created),
        "successful_creations": successful_count,
        "failed_products": failed_products,  # List of failed batch details
    }


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print("Running initialize.py...")
        # 1) Build a name → emag_category_id dict
        res = create_romania_products()
        print(res)
        # set_emag_categories_ids()
        # update_emag_fitness_products_names()
        # populate_fitness_categories()
        # populate_mappings()
