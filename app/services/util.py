import html
import re
import statistics
from typing import Dict, List
from fuzzywuzzy import fuzz


class Fitness1Product:
    def __init__(
        self,
        brand_name,
        product_name,
        category,
        image,
        label,
        barcode,
        regular_price,
        available,
        description,
    ):
        self.brand_name = brand_name
        self.product_name = product_name
        self.category = category
        self.image = image
        self.label = label
        self.barcode = barcode
        self.regular_price = regular_price
        self.available: bool = available
        self.description = description

    @classmethod
    def from_dict(cls, data):
        try:
            regular_price = float(data.get("regular_price"))
        except ValueError:
            regular_price = None
        return cls(
            data.get("brand_name"),
            data.get("product_name"),
            data.get("category"),
            data.get("image"),
            data.get("label"),
            data.get("barcode"),
            regular_price,
            data.get("available"),
            data.get("description"),
        )

    def to_dict(self):
        return {
            "brand_name": self.brand_name,
            "product_name": self.product_name,
            "category": self.category,
            "image": self.image,
            "label": self.label,
            "barcode": self.barcode,
            "regular_price": self.regular_price,
            "available": self.available,
            "description": self.description,
        }

    def __str__(self):
        return f"{self.brand_name} - {self.product_name} - {self.category} - {self.image} - {self.label} - {self.barcode} - {self.regular_price} - {self.available}"


class EmagResponse:
    def __init__(self, json_response: dict):
        self._json_response = json_response
        self.is_error: bool = json_response.get("isError", False)
        self.messages: list[str] = json_response.get("messages", [])
        self.errors: list[str] = json_response.get("errors", [])
        self.results: list = json_response.get("results", [])


class EmagStock:
    def __init__(self):
        self.warehouse_id = 1
        self.value = 100

    def to_dict(self):
        return {
            "warehouse_id": self.warehouse_id,
            "value": self.value,
        }


class EmagImage:
    def __init__(self, url: str, display_type: int):
        self.url = url
        self.display_type = display_type

    def to_dict(self):
        return {
            "url": self.url,
            "display_type": self.display_type,
        }


class EmagProduct:
    def __init__(self):
        self.id: int = None
        self.category_id: int = None
        self.ean: str = None
        self.name: str = None
        self.part_number: str = None
        self.brand: str = None
        self.images: list[EmagImage] = None
        self.status: int = None
        self.sale_price: float = None
        self.stock: EmagStock = EmagStock()
        self.min_sale_price: int = 1
        self.max_sale_price: int = 9999
        self.vat_id: int = 6
        self.description: str = None
        self.characteristics: List[Dict] = None

    def to_dict(self):
        return {
            "id": str(self.id),
            "category_id": self.category_id,
            "ean": [self.ean],
            "name": self.name,
            "part_number": self.part_number,
            "brand": self.brand,
            "images": [image.to_dict() for image in self.images],
            "status": self.status,
            "sale_price": self.sale_price,
            "min_sale_price": self.min_sale_price,
            "max_sale_price": self.max_sale_price,
            "stock": [self.stock.to_dict()],
            "vat_id": self.vat_id,
            "description": self.description,
            "characteristics": self.characteristics,
        }

    def __str__(self):
        return f"{self.id} | {self.category_id} | {self.ean} | {self.name} | {self.part_number} | {self.brand} | {self.images} | {self.status} | {self.sale_price} | {self.stock} | {self.min_sale_price} | {self.max_sale_price} | {self.vat_id} | {self.description} | {self.characteristics}"

    def __repr__(self):
        return f"{self.id} | {self.category_id} | {self.ean} | {self.name} | {self.part_number} | {self.brand} | {self.images} | {self.status} | {self.sale_price} | {self.stock} | {self.min_sale_price} | {self.max_sale_price} | {self.vat_id} | {self.description} | {self.characteristics}"


def split_list(lst: list, batch_size=15):
    """
    Example usage:

    >> my_list = list(range(1, 251))
    >> batches = split_list(my_list, 50)
    >> for batch in batches:
    >>     print(batch)
    """
    return [lst[i : i + batch_size] for i in range(0, len(lst), batch_size)]


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


def split_text_by_sentences(text, max_length=500):
    import html
    import re

    decoded_text = html.unescape(text)
    sentences = re.findall(r"[^.!?]+[.!?]+|[^.!?]+$", decoded_text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(sentence) > max_length:
            # Split the long sentence into smaller chunks
            words = sentence.split()
            temp = ""
            for word in words:
                if len(temp) + len(word) + 1 > max_length:
                    chunks.append(temp.strip())
                    temp = word + " "
                else:
                    temp += word + " "
            if temp:
                chunks.append(temp.strip())
        else:
            if len(current_chunk) + len(sentence) > max_length:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def get_fitness1_related_emag_products_based_on_ean(
    emag_products: list[dict], fitness1_products: list[dict]
):
    """
    Retrieves a list of eMAG products that are related to a given list of Fitness1 products.

    Args:
        fitness1_products (list[dict]): A list of dictionaries representing Fitness1 products,
                                        each containing a "barcode" key.
        emag_products (list[dict]): A list of dictionaries representing eMAG products,
                                    each containing an "ean" key.

    Returns:
        list: A list of eMAG products whose EAN matches a barcode of a Fitness1 product in the input list.
    """
    fitness1_product_eans = [product["barcode"] for product in fitness1_products]
    fitness1_related_emag_products = []
    for product in emag_products:
        if not product.get("ean"):
            print(f"Product {product['id']} has no EAN.")
            continue
        else:
            if product["ean"][0] in fitness1_product_eans:
                fitness1_related_emag_products.append(product)
    # Using list comprehension for a more concise approach
    # fitness1_related_emag_products = [
    #     product
    #     for product in emag_products
    #     if product["ean"][0] in fitness1_product_eans
    # ]
    return fitness1_related_emag_products


def create_emag_p_to_f1_p_map(
    emag_products: list[dict], fitness1_products: list[dict]
) -> list[tuple]:
    # Create a dictionary for quick lookup: barcode -> Fitness1 product
    """
    Maps each eMAG product to its corresponding Fitness1 product based on EAN.

    Args:
        emag_products (list[dict]): A list of dictionaries representing eMAG products,
                                    each containing an "id" and "ean" key.
        fitness1_products (list[dict]): A list of dictionaries representing Fitness1 products,
                                        each containing a "barcode" key.

    Returns:
        list[tuple]: A list of tuples where each tuple contains an eMAG product ID and
                     its corresponding Fitness1 product dictionary.
    """

    f1_mapping = {product["barcode"]: product for product in fitness1_products}

    # Build the result list using a list comprehension
    return [
        (emag_p["id"], f1_mapping[emag_p["ean"][0]])
        for emag_p in emag_products
        if emag_p["ean"][0] in f1_mapping
    ]


def update_emag_product_data(emag_p_to_f1_p_map: list[tuple]):
    """
    Updates the sale price and status of each eMAG product in the given mapping.

    Args:
        emag_p_to_f1_p_map (list[tuple]): A list of tuples, each containing an eMAG product ID and its corresponding Fitness1 product dictionary.

    Returns:
        list[dict]: A list of dictionaries, each containing the updated eMAG product data.
    """
    updated_emag_product_data = []
    for emag_p_id, f1_p in emag_p_to_f1_p_map:
        updated_emag_product_data.append(
            {
                "id": emag_p_id,
                "sale_price": f1_p["regular_price"],
                "status": f1_p["available"],
                "vat_id": 6,
            }
        )
    return updated_emag_product_data


def get_emag_product_id_by_ean(ean: str, emag_products: list[dict]) -> int:
    """
    Retrieves the ID of an eMAG product based on its EAN.

    Args:
        ean (str): The EAN of the eMAG product.
        emag_products (list[dict]): A list of dictionaries representing eMAG products,
                                    each containing an "ean" key.

    Returns:
        int: The ID of the eMAG product, or None if not found.
    """
    for product in emag_products:
        if product["ean"][0] == ean:
            return product["id"]

    return None


def get_emag_part_number_by_ean(ean: str, emag_products: list[dict]) -> str:
    """
    Retrieves the part number of an eMAG product based on its EAN.

    Args:
        ean (str): The EAN of the eMAG product.
        emag_products (list[dict]): A list of dictionaries representing eMAG products,
                                    each containing an "ean" key.

    Returns:
        str: The part number of the eMAG product, or None if not found.
    """
    for product in emag_products:
        if product["ean"][0] == ean:
            return product["part_number"]

    return None


def get_current_emag_products_categories(emag_products: list[dict]) -> list:
    """
    Retrieves a list of unique category IDs from a list of eMAG products.

    Args:
        emag_products (list[dict]): A list of dictionaries representing eMAG products,
                                    each containing a "category_id" key.

    Returns:
        list: A list of unique category IDs extracted from the input products.
    """

    return list(set([product["category_id"] for product in emag_products]))


def get_current_fitness1_categories(fitness1_products: list[dict]) -> list:
    """
    Retrieves a list of unique category IDs from a list of Fitness1 products.

    Args:
        fitness1_products (list[dict]): A list of dictionaries representing Fitness1 products,
                                        each containing a "category" key.

    Returns:
        list: A list of unique category IDs extracted from the input products.
    """

    return list(
        set(
            [
                product["category"]
                for product in fitness1_products
                if product["category"]
            ]
        )
    )


def build_url(
    base_url: str, url_ext: str = "bg", resource: str = None, action: str = None
) -> str:
    """
    Constructs a URL using the base URL, a given resource, and an action.

    Args:
        base_url (str): The EMAG API base URL
        resource (str): The API resource (e.g., "product_offer", "category").
        action (str): The action to perform (e.g., "read", "save").

    Returns:
        str: The full URL.
    """
    url = base_url.format(url_ext)
    return f"{url}/{resource}/{action}"


def get_subcategories(fitness1_cat: str):
    """Split a fitness1 category string into subcategories (tokens).

    Args:
        fitness1_cat (str): The fitness1 category string to split.

    Returns:
        list: A list of subcategory tokens.
    """
    # Split on '>' and also split on '/' if needed (since some categories have "/" as separators)
    tokens = []
    for part in fitness1_cat.split(">"):
        # Further split by '/' or ':' to catch alternative naming conventions
        sub_parts = re.split(r"[/:]", part)
        tokens.extend([sub.strip() for sub in sub_parts if sub.strip()])
    return tokens


def preprocess(text: str):
    """Lowercase and remove punctuation for normalization."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text


def is_match(emag_category, token, threshold, keywords_mapping):
    """
    Check if a emag category matches a given token (i.e., a substring of a fitness category)
    by doing a fuzzy match (using both token_set_ratio and partial_ratio) and by checking
    if the token contains any of the category's keywords.

    Parameters:
        emag_category (str): emag category name
        token (str): token to check
    Returns:
        bool: True if the token is a match, False otherwise
    """
    token_clean = preprocess(token)  # e.g., lowercasing & removing punctuation
    ec_clean = preprocess(emag_category)

    # Check keyword boost if defined for this small category.
    if emag_category in keywords_mapping:
        for kw in keywords_mapping[emag_category]:
            if kw in token_clean:
                return True

    # Otherwise, you can combine fuzzy metrics and substring checks as before.
    if ec_clean in token_clean or token_clean in ec_clean:
        return True
    score1 = fuzz.token_set_ratio(ec_clean, token_clean)
    score2 = fuzz.partial_ratio(ec_clean, token_clean)
    avg_score = (score1 + score2) / 2
    return avg_score >= threshold


def build_mapping(
    fitness1_categories: list,
    emag_categories: list,
    threshold: int,
    keywords_mapping: dict,
):
    """
    Build a dictionary mapping each emag category to a list of matching fitness1 categories.
    Parameters:
      - fitness1_categories: set (or list) of fitness1 category strings.
      - emag_categories: list of emag category strings.
      - threshold: the fuzzy matching threshold.
      - keywords_mapping: dict mapping emag categories to keyword lists.
    Returns:
      A dict where keys are emag categories and values are lists of matching fitness1 categories.
    """
    mapping = {emag_cat: [] for emag_cat in emag_categories}
    matched_fitness1_cats = (
        set()
    )  # to track which fitness1 categories have been matched

    for fitness1_cat in fitness1_categories:
        if not fitness1_cat.strip():
            continue  # Skip empty strings.
        tokens = get_subcategories(fitness1_cat)
        matched = False
        for emag_cat in emag_categories:
            if any(
                is_match(emag_cat, token, threshold, keywords_mapping)
                for token in tokens
            ):
                mapping[emag_cat].append(fitness1_cat)
                matched = True
        if matched:
            matched_fitness1_cats.add(fitness1_cat)
    return mapping


def map_fitness1_category_to_emag_category_string(mapping: dict):
    """
    Given a mapping of emag_category: [list of fitness1_categories],
    invert it to produce a mapping of fitness1_category: emag_category
    that matched that big category.
    """
    inverse = {}
    for emag_cat, fitness1_cat_list in mapping.items():
        for fitness1_cat in fitness1_cat_list:
            inverse[fitness1_cat] = emag_cat
    return inverse


def map_fitness1_category_to_emag_category_data(
    mapped_categories_strings: dict, emag_categories: list
):
    """
    Given a mapping of fitness1_category: emag_category,
    produce a mapping of fitness1_category: emag_category_data from the emag_categories list
    Returns a dictionary where keys are fitness1 categories and values are emag category data.
    """
    f1_to_emag_cat = {}
    for fitness1_cat, emag_cat in mapped_categories_strings.items():
        for category in emag_categories:
            if category["name"] == emag_cat:
                f1_to_emag_cat[fitness1_cat] = category
    return f1_to_emag_cat


def get_emag_category_data_by_fitness1_category(
    f1_to_emag_mapping: dict, fitness1_category: str
) -> dict:
    """
    Retrieves the emag category data corresponding to a given fitness1 category.

    Args:
        f1_to_emag_mapping (dict): A dictionary mapping fitness1 categories to emag categories data.
        fitness1_category (str): The fitness1 category for which to find the corresponding emag category.

    Returns:
        The emag category data corresponding to the given fitness1 category, or None if not found.
    """
    return f1_to_emag_mapping.get(fitness1_category)


def get_fitness_related_emag_categories(
    emag_categories: list, fitness_categories: list
) -> dict:
    """
    Gets the fitness (not fitness1) categories  from the emag categories list

    Args:
        emag_categories (list): The list of emag categories to map.
        fitness_categories (list): The list of fitness categories to map.

    Returns:
        list: A list of emag categories that match the fitness categories.
    """

    return [
        category
        for category in emag_categories
        if category["name"] in fitness_categories
    ]


def get_fitness1_products_with_mapped_categories(
    fitness1_products: list, mapped_categories_strings: dict
):
    """
    Filters a list of fitness1 products to only include those with categories that have a mapped emag category.

    Args:
        fitness1_products (list): The list of fitness1 products to filter.
        mapped_categories_strings (dict): A dictionary mapping fitness1 categories to emag categories.

    Returns:
        list: A list of fitness1 products with categories that have a mapped emag category.
    """
    return [
        product
        for product in fitness1_products
        if product["category"] in mapped_categories_strings.keys()
    ]


def get_id_and_outliers(data, factor=3):
    # Handle empty list case
    if not data or not isinstance(data, list):
        print("Empty data list provided.")
        return None, []

    # Step 1: Compute the median of the data
    median_val = statistics.median(data)

    # Step 2: Compute absolute deviations from the median
    deviations = [abs(x - median_val) for x in data]

    # Step 3: Compute the median absolute deviation (MAD)
    mad = statistics.median(deviations)

    # Step 4: Identify non-outliers and outliers based on a factor * MAD threshold
    non_outliers = [x for x in data if abs(x - median_val) <= factor * mad]
    outliers = [x for x in data if abs(x - median_val) > factor * mad]

    # Step 5: Choose the next id as one greater than the maximum of the non-outlier values
    new_id = max(non_outliers) + 1 if non_outliers else None

    return max(non_outliers), new_id, outliers


def get_valid_emag_product_id(emag_products_ids: list):
    """
    Returns the next available id for an emag product
    """
    last_10_ids = emag_products_ids[-10:]
    latest_id, new_id, outliers = get_id_and_outliers(last_10_ids)
    # insert the new id next to the place of where the last_id is
    emag_products_ids.insert(emag_products_ids.index(latest_id) + 1, new_id)
    return new_id


def create_emag_product_from_fitness1_product(
    fitness1_product: Fitness1Product,
) -> EmagProduct:
    """
    Creates an EmagProduct from a Fitness1Product.
    Sets the:
    \n
        - brand
        - name
        - ean
        - sale_price
        - description
        - images
        - status
    \n
    To be set is:
    \n
        - id
        - category_id
        - part_number

    Args:
        fitness1_product (Fitness1Product): The Fitness1Product to convert.

    Returns:
        EmagProduct: The EmagProduct created from the given Fitness1Product.
    """

    emag_product = EmagProduct()
    emag_images = [
        EmagImage(url=fitness1_product.image, display_type=1),
        EmagImage(url=fitness1_product.label, display_type=2),
    ]

    emag_product.brand = fitness1_product.brand_name
    emag_product.name = fitness1_product.product_name
    emag_product.ean = fitness1_product.barcode
    emag_product.sale_price = fitness1_product.regular_price
    emag_product.description = html.unescape(fitness1_product.description)
    emag_product.images = emag_images
    emag_product.status = True if fitness1_product.available else False
    return emag_product
