import json
import time

import requests

from app.logger import add_log
from app.services import const, util


def fetch_all_emag_products(api_url: str, headers: dict, pause: int = 0) -> list:
    """
    Fetches all products from a given API URL with pagination.

    Args:
        api_url (str): The API URL to query.
        headers (dict): The headers to include in the request.
        pause (int, optional): The number of seconds to pause between requests. Defaults to 0.

    Returns:
        list: A list of products fetched from the API.
    """
    page = 1  # starting page
    items_per_page = 100  # number of items per page
    all_products = []
    result = True

    while True:
        # Set up parameters for pagination
        payload = {"currentPage": page, "itemsPerPage": items_per_page}
        response = requests.post(api_url, json=payload, headers=headers)

        # Check for a successful request
        if response.status_code != 200:
            add_log(
                f"Request failed at page {page} with status: {response.status_code}"
            )
            result = False
            break
        data = response.json()
        if data["isError"]:

            add_log(
                f"Request failed at page >>{page}<< with messages: {data['messages']} and errors: {data['errors']}"
            )
            result = False

        # Parse the JSON response
        products = data.get("results", [])
        add_log(f"Request successful at page {page}")

        # If the products list is empty, we've reached the end
        if not products:
            add_log(f"No products found on page {page}. Ending pagination.")
            break

        # Append the products from the current page to our total list
        all_products.extend(products)
        if not all_products:
            result = False
        add_log(f"Fetched {len(products)} products from page {page}")

        # Move to the next page
        page += 1
        time.sleep(pause)

    return result, all_products


def fetch_all_fitness1_products(api_url: str, api_key: str) -> list:
    """
    Fetches all products from a given API URL with a given API key.

    Args:
        api_url (str): The API URL to query.
        api_key (str): The API key to include in the request.

    Returns:
        list: A list of products fetched from the API.
    """
    response = requests.get(api_url, params={"key": api_key, "description": "1"})

    # Check for a successful request
    if response.status_code != 200:
        add_log(f"Request failed with status code: {response.status_code}")
        return
    data = response.json()
    if data.get("status") not in ["ok"]:
        add_log(f"Request failed with data {data}")
        return

    return data.get("products")


def fetch_all_categories_from_categories_list_emag(
    api_url: str, headers: dict, categories_list: list, pause: int = 0
) -> list:
    """
    Fetches all categories from a list of category IDs by making API requests.

    Args:
        api_url (str): The API URL to query.
        headers (dict): The headers to include in the request.
        categories_list (list): A list of category IDs to fetch.
        pause (int, optional): The number of seconds to pause between requests. Defaults to 0.

    Returns:
        list: A list of categories fetched from the API.
    """

    all_categories = []

    # Set up parameters for pagination
    for category in categories_list:
        payload = {"id": category}
        response = requests.post(api_url, json=payload, headers=headers)

        # Check for a successful request
        if response.status_code != 200:
            add_log(
                f"Request failed for category {category} with status: {response.status_code}"
            )
            break
        data = response.json()
        if data["isError"]:

            add_log(
                f"Request failed for category >>{category}<< with messages: {data['messages']} and errors: {data['errors']}"
            )

        # Parse the JSON response
        category_data = data.get("results", [])
        add_log(f"Request successful for category {category}")

        # If the products list is empty, we've reached the end
        if not category_data:
            add_log("No category data found.")
            break

        # Append the products from the current page to our total list
        all_categories.extend(category_data)

        # Move to the next page
        time.sleep(pause)

    add_log(f"Fetched {len(all_categories)} categories")
    return all_categories


def create_emag_product_from_fields(
    fitness1_product: util.Fitness1Product,
    fitness1_related_emag_products_based_on_ean: list[dict],
    all_emag_product_ids: list[int],
    f1_to_emag_categories: dict,
):
    emag_product = util.create_emag_product_from_fitness1_product(fitness1_product)
    if emag_product.ean in [
        product["ean"][0] for product in fitness1_related_emag_products_based_on_ean
    ]:
        # get the id of the found product and set it to the emag product
        emag_product.id = util.get_emag_product_id_by_ean(
            emag_product.ean, fitness1_related_emag_products_based_on_ean
        )
        emag_product.part_number = util.get_emag_part_number_by_ean(
            emag_product.ean, fitness1_related_emag_products_based_on_ean
        )
    else:
        emag_product.id = util.get_valid_emag_product_id(all_emag_product_ids)
    emag_product.category_id = util.get_emag_category_data_by_fitness1_category(
        f1_to_emag_categories, fitness1_product.category
    ).get("id")
    emag_product.part_number = f"IDCARS-{emag_product.id}"
    return emag_product


def post_emag_product(
    emag_product_data: list[dict],
    api_url: str,
    headers: dict,
    pause=0,
    batch_size=50,
):
    batched_emag_products_data = util.split_list(
        emag_product_data, batch_size=batch_size
    )
    failed_products = []
    for i, batch in enumerate(batched_emag_products_data):

        time.sleep(pause)
        response = requests.post(api_url, json=batch, headers=headers)
        if not response.ok:
            add_log(f"Request failed with status: {response.status_code}")
        add_log(response.json())
        data = util.EmagResponse(response.json())

        if data.is_error:
            add_log(
                f"Request failed >>{batch}<< with messages: {data.messages} and errors: {data.errors}"
            )
            failed_products.append(
                {
                    "batch": i,
                    "emag_product_data": batch,
                    "messages": data.messages,
                    "errors": data.errors,
                }
            )
            # return data

    add_log(f"Request successful for product {emag_product_data}")
    return failed_products


def run():
    all_emag_products = fetch_all_emag_products(
        api_url=util.build_url(const.EMAG_URL, "product_offer", "read"),
        headers=const.EMAG_HEADERS,
        pause=1,
    )

    add_log(f"Fetched {len(all_emag_products)} EMAG products")

    all_fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    add_log(f"Fetched {len(all_fitness1_products)} Fitness1 products")

    fitness1_related_emag_products_based_on_ean = (
        util.get_fitness1_related_emag_products_based_on_ean(
            all_emag_products, all_fitness1_products
        )
    )
    rest_emag_products = [
        emag_product
        for emag_product in all_emag_products
        if emag_product not in fitness1_related_emag_products_based_on_ean
    ]

    current_emag_products_categories = util.get_current_emag_products_categories(
        rest_emag_products
    )

    all_emag_categories = fetch_all_categories_from_categories_list_emag(
        api_url=util.build_url(const.EMAG_URL, "category", "read"),
        headers=const.EMAG_HEADERS,
        categories_list=current_emag_products_categories,
        pause=1,
    )

    all_fitness_emag_categories = util.get_fitness_related_emag_categories(
        all_emag_categories, const.FITNESS_CATEGORIES
    )

    all_fitness1_categories = util.get_current_fitness1_categories(
        all_fitness1_products
    )

    all_emag_categories_names = [
        emag_category["name"] for emag_category in all_fitness_emag_categories
    ]

    categories_mapping = util.build_mapping(
        fitness1_categories=all_fitness1_categories,
        emag_categories=all_emag_categories_names,
        threshold=80,
        keywords_mapping=const.KEYWORDS_MAPPING,
    )
    mapped_categories_strings = util.map_fitness1_category_to_emag_category_string(
        categories_mapping
    )

    valid_fitness1_products_data = util.get_fitness1_products_with_mapped_categories(
        all_fitness1_products, mapped_categories_strings
    )  # used to create emag products
    valid_fitness1_products = [
        util.Fitness1Product.from_dict(product)
        for product in valid_fitness1_products_data
    ]

    f1_to_emag_categories = util.map_fitness1_category_to_emag_category_data(
        mapped_categories_strings, all_fitness_emag_categories
    )
    all_emag_product_ids = [emag_product["id"] for emag_product in all_emag_products]
    emag_products: list[util.EmagProduct] = []
    for fitness1_product in valid_fitness1_products:
        emag_product = create_emag_product_from_fields(
            fitness1_product,
            fitness1_related_emag_products_based_on_ean,
            all_emag_product_ids,
            f1_to_emag_categories,
        )
        emag_products.append(emag_product)
    add_log(f"Created {len(emag_products)} EMAG products")

    failed_products = post_emag_product(
        emag_product_data=[emag_product.to_dict() for emag_product in emag_products],
        api_url=util.build_url(const.EMAG_URL, "product_offer", "save"),
        headers=const.EMAG_HEADERS,
        pause=2,
    )

    add_log(f"Created {len(emag_products) - len(failed_products)} EMAG products")
    with open("failed_products.json", "w") as f:
        json.dump(failed_products, f, indent=4)
        add_log("Failed products saved to failed_products.json")


def update_emag_products(batch_size=50, pause=1):
    all_emag_products = fetch_all_emag_products(
        api_url=util.build_url(const.EMAG_URL, "product_offer", "read"),
        headers=const.EMAG_HEADERS,
        pause=1,
    )

    add_log(f"Fetched {len(all_emag_products)} EMAG products")

    all_fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    add_log(f"Fetched {len(all_fitness1_products)} Fitness1 products")

    emag_p_to_f1_p_map = util.create_emag_p_to_f1_p_map(
        all_emag_products, all_fitness1_products
    )

    updated_emag_product_data = util.update_emag_product_data(emag_p_to_f1_p_map)
    batched_updated_emag_product_data = util.split_list(
        updated_emag_product_data, batch_size=batch_size
    )

    failed_updates = []

    for i, batch in enumerate(batched_updated_emag_product_data):
        time.sleep(pause)
        response = requests.post(
            util.build_url(const.EMAG_URL, "product_offer", "save"),
            json=batch,
            headers=const.EMAG_HEADERS,
        )
        if not response.ok:
            add_log(f"Request failed with status: {response.status_code}")
        add_log(response.json())
        data = util.EmagResponse(response.json())

        if data.is_error:
            add_log(
                f"Request failed >>{batch}<< with messages: {data.messages} and errors: {data.errors}"
            )
            failed_updates.append(
                {
                    "batch": i,
                    "emag_product_data": batch,
                    "messages": data.messages,
                    "errors": data.errors,
                }
            )

    add_log(
        f"Updated {len(updated_emag_product_data) - len(failed_updates)} EMAG products"
    )
    with open("failed_updates.json", "w") as f:
        json.dump(failed_updates, f, indent=4)
        add_log("Failed updates saved to failed_updates.json")


def run_create_process(pause=1, batch_size=50):
    """
    Executes the complete create process.

    This function performs the following steps:
      1. Fetches all EMAG products from the API using pagination.
      2. Fetches all Fitness1 products.
      3. Determines which EMAG products are related to Fitness1 products (based on EAN matching).
      4. Fetches the current EMAG product categories and then retrieves detailed category data.
      5. Builds a mapping between Fitness1 categories and EMAG categories.
      6. Filters the Fitness1 products to include only those with mapped categories.
      7. Converts the filtered Fitness1 products to objects.
      8. Creates new EMAG product objects by merging data from Fitness1 and EMAG.
      9. Posts the created EMAG products in batches.

    Parameters:
      pause (int): Number of seconds to pause between API requests.
      batch_size (int): Number of products to include in each batch when posting.

    Returns:
      dict: A summary of the process, including counts of fetched products, created products,
            and details about any failed posts.
    """

    add_log("Starting product creation process...")

    # Step 1: Fetch all EMAG products
    emag_products_result, emag_products_fetched = fetch_all_emag_products(
        api_url=util.build_url(const.EMAG_URL, "product_offer", "read"),
        headers=const.EMAG_HEADERS,
        pause=pause,
    )
    if not emag_products_result:
        add_log("Failed to fetch EMAG products.")
        return {"emag_products_fetched": len(emag_products_fetched)}
    add_log(f"Fetched {len(emag_products_fetched)} EMAG products.")

    # Step 2: Fetch all Fitness1 products
    fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    add_log(f"Fetched {len(fitness1_products)} Fitness1 products.")

    # Step 3: Determine related EMAG products based on matching EAN (barcode)
    fitness1_related_emag_products = (
        util.get_fitness1_related_emag_products_based_on_ean(
            emag_products_fetched, fitness1_products
        )
    )
    add_log(
        f"Fetched {len(fitness1_related_emag_products)} Fitness1 related EMAG products."
    )

    # Step 4: Get current EMAG categories from the remaining products
    current_emag_categories = util.get_current_emag_products_categories(
        emag_products_fetched
    )
    add_log(f"Fetched {len(current_emag_categories)} EMAG categories.")

    # Fetch detailed EMAG category data
    all_emag_categories = fetch_all_categories_from_categories_list_emag(
        api_url=util.build_url(const.EMAG_URL, "category", "read"),
        headers=const.EMAG_HEADERS,
        categories_list=current_emag_categories,
        pause=pause,
    )
    add_log(f"Fetched {len(all_emag_categories)} EMAG categories.")

    # Step 5: Filter to obtain only Fitness-related EMAG categories and all unique Fitness1 categories
    all_fitness_emag_categories = util.get_fitness_related_emag_categories(
        all_emag_categories, const.FITNESS_CATEGORIES
    )
    all_fitness1_categories = util.get_current_fitness1_categories(fitness1_products)

    # Extract category names from the detailed EMAG categories
    emag_categories_names = [
        category["name"] for category in all_fitness_emag_categories
    ]

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

    # Step 7: Filter Fitness1 products to include only those with a mapped EMAG category
    valid_fitness1_products_data = util.get_fitness1_products_with_mapped_categories(
        fitness1_products, mapped_categories_strings
    )
    valid_fitness1_products = [
        util.Fitness1Product.from_dict(product)
        for product in valid_fitness1_products_data
    ]

    # Step 8: Map each Fitness1 product to its corresponding EMAG category data
    f1_to_emag_categories = util.map_fitness1_category_to_emag_category_data(
        mapped_categories_strings, all_fitness_emag_categories
    )

    # Get all existing EMAG product IDs (for generating a valid new ID if needed)
    all_emag_product_ids = [product["id"] for product in emag_products_fetched]

    # Step 9: Create new EMAG products by merging data from Fitness1 with EMAG category info
    emag_products_created = []
    for fitness1_product in valid_fitness1_products:
        emag_product = create_emag_product_from_fields(
            fitness1_product,
            fitness1_related_emag_products,
            all_emag_product_ids,
            f1_to_emag_categories,
        )
        emag_products_created.append(emag_product)
    add_log(f"Created {len(emag_products_created)} EMAG product objects.")

    # Step 10: Post the created EMAG products in batches
    # Note: The post_emag_product function should already handle splitting into batches.
    products_data = [product.to_dict() for product in emag_products_created]
    failed_products = post_emag_product(
        emag_product_data=products_data,
        api_url=util.build_url(const.EMAG_URL, "product_offer", "save"),
        headers=const.EMAG_HEADERS,
        pause=pause * 2,
        batch_size=batch_size,
    )

    successful_count = len(emag_products_created) - len(failed_products)
    add_log(
        f"Successfully posted {successful_count} EMAG products, {len(failed_products)} failed."
    )

    # Instead of writing to a file, return a summary dictionary
    return {
        "emag_products_fetched": len(emag_products_fetched),
        "fitness1_products_fetched": len(fitness1_products),
        "emag_categories_fetched": len(all_emag_categories),
        "emag_products_created": len(emag_products_created),
        "successful_creations": successful_count,
        "failed_products": failed_products,  # List of failed batch details
    }


def run_update_process(pause=1, batch_size=50):
    """
    Optimized version of the update process with streaming.
    """

    add_log("Starting product update process...")

    # Step 1: Fetch all Fitness1 products once
    fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    if not fitness1_products:
        add_log("Failed to fetch Fitness1 products.")
        return {"fitness1_products_fetched": 0}

    add_log(f"Fetched {len(fitness1_products)} Fitness1 products.")

    # Create a lookup table for Fitness1 products by barcode
    fitness1_index = {product["barcode"]: product for product in fitness1_products}

    # Step 2: Stream EMAG products page by page
    page = 1
    items_per_page = 100  # or whatever you want
    total_emag_products = 0
    total_updates = 0
    failed_batches = []

    while True:
        # Fetch one page of EMAG products
        payload = {"currentPage": page, "itemsPerPage": items_per_page}
        response = requests.post(
            url=util.build_url(const.EMAG_URL, "product_offer", "read"),
            json=payload,
            headers=const.EMAG_HEADERS,
        )

        if response.status_code != 200:
            add_log(
                f"Failed to fetch EMAG products at page {page}. Status: {response.status_code}"
            )
            break

        data = response.json()

        if data.get("isError", False):
            add_log(f"Error fetching page {page}: {data.get('messages', [])}")
            break

        emag_products = data.get("results", [])

        if not emag_products:
            add_log(f"No more products found on page {page}. Ending pagination.")
            break

        total_emag_products += len(emag_products)
        add_log(f"Fetched {len(emag_products)} EMAG products on page {page}.")

        # Map EMAG products to Fitness1 products
        update_batch = []
        for emag_product in emag_products:
            ean_list = emag_product.get("ean", [])
            if not ean_list:
                continue  # skip products without EAN

            barcode = ean_list[0]
            fitness1_product = fitness1_index.get(barcode)

            if fitness1_product:
                # Build update entry
                update_batch.append(
                    {
                        "id": emag_product["id"],
                        "sale_price": fitness1_product["regular_price"],
                        "status": fitness1_product["available"],
                        "vat_id": 6,
                    }
                )

        # Split into smaller batches
        batched_updates = util.split_list(update_batch, batch_size)

        # Send each batch
        for i, batch in enumerate(batched_updates):
            if not batch:
                continue
            add_log(f"Posting batch {i+1} of {len(batched_updates)} on page {page}...")
            time.sleep(pause)

            save_response = requests.post(
                url=util.build_url(const.EMAG_URL, "product_offer", "save"),
                json=batch,
                headers=const.EMAG_HEADERS,
            )

            if not save_response.ok:
                add_log(
                    f"Save failed for batch {i+1} on page {page}. Status: {save_response.status_code}"
                )
                failed_batches.append(
                    {
                        "page": page,
                        "batch": i + 1,
                        "status_code": save_response.status_code,
                        "response": save_response.text,
                    }
                )
                continue

            save_data = util.EmagResponse(save_response.json())
            if save_data.is_error:
                add_log(
                    f"Errors in batch {i+1} on page {page}: {save_data.messages} {save_data.errors}"
                )
                failed_batches.append(
                    {
                        "page": page,
                        "batch": i + 1,
                        "errors": save_data.errors,
                        "messages": save_data.messages,
                    }
                )
            else:
                total_updates += len(batch)

        page += 1  # go to next page

    add_log(
        f"Update process completed: {total_updates} successful updates, {len(failed_batches)} failed batches."
    )

    return {
        "fitness1_products_fetched": len(fitness1_products),
        "emag_products_fetched": total_emag_products,
        "updated_entries": total_updates,
        "failed_updates": failed_batches,
    }
