"""
Maps a Blogger article's free-form labels to one of the site's five
confirmed clusters. Keyword lists are intentionally broad (case-insensitive
substring match against each label) since Blogger labels are inconsistent
in casing/phrasing.
"""

CLUSTERS = {
    "digital-intelligence": {
        "name": "Digital Intelligence",
        "keywords": [
            "artificial intelligence", "ai ", " ai", "machine learning", "deep learning",
            "agentic", "llm", "generative ai", "neural network", "chatbot", "anthropic",
            "claude", "openai", "gpt", "cybersecurity", "security", "encryption",
            "robotics", "robot", "automation", "autonomous", "software", "coding",
            "computer vision", "nlp", "data science", "algorithm",
        ],
    },
    "frontier-technologies": {
        "name": "Frontier Technologies",
        "keywords": [
            "quantum", "semiconductor", "chip", "transistor", "materials science",
            "nanotechnology", "photonics", "superconduct", "spintronics", "memristor",
            "neuromorphic", "circuit", "silicon", "hardware", "computing architecture",
            "3d printing", "advanced materials", "graphene",
        ],
    },
    "human-future": {
        "name": "Human Future",
        "keywords": [
            "biotech", "health", "medical", "medicine", "disease", "cancer", "drug",
            "genome", "gene", "dna", "rna", "brain", "neuroscience", "cognitive",
            "biology", "cell", "protein", "vaccine", "surgery", "diagnosis", "therapy",
            "wearable", "prosthetic", "longevity", "clinical", "patient", "physics",
            "cosmology", "particle", "fundamental science",
        ],
    },
    "sustainable-future": {
        "name": "Sustainable Future",
        "keywords": [
            "clean energy", "solar", "renewable", "battery", "climate", "carbon",
            "sustainab", "emission", "environment", "recycl", "green tech", "ev ",
            "electric vehicle", "wind power", "hydrogen fuel", "hydrogen energy",
            "fuel cell", "biofuel",
        ],
    },
    "india-society": {
        "name": "India & Society",
        "keywords": [
            "india", "policy", "government", "defence", "defense", "military",
            "geopolit", "economy", "startup", "enterprise", "regulation", "society",
            "space program", "isro", "national security", "innovation gap",
        ],
    },
}

DEFAULT_CLUSTER = "digital-intelligence"


def get_cluster(labels, title="", text=""):
    """Return (cluster_slug, cluster_name) for an article given its Blogger
    labels (list of strings), title, and body text. Title matches are
    weighted more heavily since they're the strongest topical signal and
    resolve ties between equally-matched label sets."""

    labels_haystack = " ".join(labels).lower()
    title_haystack = title.lower()
    body_haystack = text[:600].lower()

    scores = {}
    for slug, info in CLUSTERS.items():
        score = 0.0
        for kw in info["keywords"]:
            if kw in title_haystack:
                score += 3
            if kw in labels_haystack:
                score += 2
            if kw in body_haystack:
                score += 1
        if score:
            scores[slug] = score

    if not scores:
        return DEFAULT_CLUSTER, CLUSTERS[DEFAULT_CLUSTER]["name"]

    best = max(scores, key=scores.get)
    return best, CLUSTERS[best]["name"]


def cluster_list():
    """Ordered list of (slug, name) for nav/footer/homepage rendering."""
    order = [
        "digital-intelligence",
        "frontier-technologies",
        "human-future",
        "sustainable-future",
        "india-society",
    ]
    return [(slug, CLUSTERS[slug]["name"]) for slug in order]
