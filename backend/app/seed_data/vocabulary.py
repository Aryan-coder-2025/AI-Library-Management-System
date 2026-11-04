"""Deterministic synthetic data vocabulary and distributions for library demo data."""
from typing import Dict, List, Tuple

# ── User Generation Vocabulary ────────────────────────────────────────────────

FIRST_NAMES: List[str] = [
    "Alan", "Ada", "Grace", "Claude", "Tim", "Margaret", "Donald", "Edsger", "Barbara",
    "John", "Leslie", "Shafi", "Silvio", "Geoffrey", "Yann", "Yoshua", "Demis", "Fei-Fei",
    "Andrew", "Radia", "Ken", "Dennis", "Bjarne", "Guido", "Linus", "James", "Brendan",
    "Anita", "Vint", "Bob", "Stephen", "Richard", "Peter", "David", "Michael", "Robert",
    "William", "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark",
    "Elizabeth", "Jennifer", "Maria", "Susan", "Margaret", "Dorothy", "Lisa", "Nancy",
    "Karen", "Betty", "Helen", "Sandra", "Donna", "Carol", "Ruth", "Sharon", "Michelle",
    "Laura", "Sarah", "Kimberly", "Deborah", "Jessica", "Shirley", "Cynthia", "Angela",
    "Melissa", "Brenda", "Amy", "Anna", "Rebecca", "Virginia", "Kathleen", "Pamela",
    "Martha", "Debra", "Amanda", "Stephanie", "Carolyn", "Christine", "Marie", "Janet",
    "Catherine", "Frances", "Ann", "Joyce", "Diane", "Alice", "Julie", "Heather", "Teresa",
    "Doris", "Gloria", "Evelyn", "Jean", "Cheryl", "Mildred", "Katherine", "Joan", "Ashley",
    "Judith", "Rose", "Janice", "Kelly", "Nicole", "Judy", "Christina", "Kathy", "Theresa",
    "Beverly", "Denise", "Tammy", "Irene", "Jane", "Lori", "Rachel", "Marilyn", "Andrea",
    "Kathryn", "Louise", "Sara", "Anne", "Jacqueline", "Wanda", "Bonnie", "Julia", "Ruby",
    "Lois", "Tina", "Phyllis", "Norma", "Paula", "Diana", "Annie", "Lillian", "Emily",
    "Robin", "Peggy", "Crystal", "Gladys", "Rita", "Dawn", "Connie", "Florence", "Tracy",
    "Edna", "Tiffany", "Carmen", "Rosa", "Cindy", "Grace", "Wendy", "Victoria", "Edith",
    "Kim", "Sherry", "Sylvia", "Josephine", "Thelma", "Shannon", "Sheila", "Ethel", "Ellen",
    "Elaine", "Marjorie", "Carrie", "Charlotte", "Monica", "Esther", "Pauline", "Emma",
    "Juanita", "Anita", "Rhonda", "Hazel", "Amber", "Eva", "Debbie", "April", "Leslie",
    "Clara", "Lucille", "Jamie", "Joanne", "Eleanor", "Valerie", "Danielle", "Megan", "Alicia",
    "Suzanne", "Michele", "Gail", "Bertha", "Darlene", "Veronica", "Jill", "Erin", "Geraldine",
    "Lauren", "Cathy", "Joann", "Lorraine", "Lynn", "Sally", "Regina", "Erica", "Beatrice",
    "Dolores", "Bernice", "Audrey", "Yvonne", "Annette", "June", "Samantha", "Marion", "Dana",
]

LAST_NAMES: List[str] = [
    "Turing", "Lovelace", "Hopper", "Shannon", "Berners-Lee", "Hamilton", "Knuth", "Dijkstra",
    "Liskov", "von Neumann", "Lamport", "Goldwasser", "Micali", "Hinton", "LeCun", "Bengio",
    "Hassabis", "Li", "Ng", "Perlman", "Thompson", "Ritchie", "Stroustrup", "van Rossum",
    "Torvalds", "Gosling", "Eich", "Borg", "Cerf", "Kahn", "Cook", "Karp", "Rivest", "Shamir",
    "Adleman", "Diffie", "Hellman", "Merkle", "Backus", "McCarthy", "Minsky", "Engelbart",
    "Sutherland", "Brooks", "Patterson", "Hennessy", "Codd", "Stonebraker", "Gray", "Tarjan",
    "Hopcroft", "Ullman", "Aho", "Corbato", "Wilkes", "Perlis", "Hamming", "Floyd", "Iverson",
    "Naur", "Wirth", "Cocke", "Rabin", "Scott", "Milner", "Pnueli", "Valiant", "Stearns",
    "Hartmanis", "Reddy", "Feigenbaum", "Sifakis", "Clarke", "Emerson", "Lipton", "Kearns",
    "Vazirani", "Papadimitriou", "Sipser", "Sedgewick", "Kleinberg", "Tardos", "Russell", "Norvig",
    "Goodfellow", "Sutskever", "Silver", "Schmidhuber", "Marcus", "Tenembaum", "Bottou", "Vapnik",
    "Cortes", "Breiman", "Quinlan", "Hastie", "Tibshirani", "Friedman", "Bishop", "Murphy",
    "Koller", "Friedman", "Jordan", "Blei", "Wainwright", "Boyd", "Vandenberghe", "Nocedal",
]

DEPARTMENTS: List[str] = [
    "Computer Science", "Mathematics", "Electrical Engineering", "Physics",
    "Data Science & AI", "Mechanical Engineering", "Biomedical Engineering",
    "Philosophy & Logic", "Economics & Finance", "Information Systems",
    "Cognitive Science", "Statistics & Probability",
]

# ── Catalogue Generation Vocabulary ───────────────────────────────────────────

CATEGORIES: List[str] = [
    "Computer Science", "Mathematics", "Artificial Intelligence", "Physics",
    "Software Engineering", "Algorithms & Complexity", "Data Science",
    "Cybersecurity & Cryptography", "Distributed Systems", "Robotics",
    "Philosophy of Technology", "Information Systems",
]

TITLE_PREFIXES: List[str] = [
    "Introduction to", "Advanced", "Principles of", "Foundations of", "Handbook of",
    "Modern", "Applied", "Essential", "Theoretical", "Comprehensive", "Mastering",
    "Understanding", "Elements of", "Guide to", "Concepts in", "Design and Analysis of",
    "The Architecture of", "Statistical", "Computational", "Probabilistic",
]

TITLE_TOPICS: List[str] = [
    "Algorithms", "Neural Networks", "Deep Learning", "Quantum Computing", "Database Systems",
    "Operating Systems", "Computer Architecture", "Discrete Mathematics", "Linear Algebra",
    "Cryptographic Protocols", "Distributed Consensus", "Information Retrieval", "Machine Learning",
    "Reinforcement Learning", "Graph Theory", "Automata Theory", "Compiler Design",
    "Computer Networks", "Cybersecurity", "Natural Language Processing", "Computer Vision",
    "Convex Optimization", "Stochastic Processes", "Knowledge Representation", "Robotics Dynamics",
    "Cloud Computing Systems", "Parallel Programming", "Software Verification", "Bioinformatics",
    "Embedded Systems", "Statistical Inference", "Complex Systems", "Microservices Architecture",
]

TITLE_SUFFIXES: List[str] = [
    "A Modern Approach", "Theory and Practice", "In Depth", "From First Principles",
    "For Engineers and Scientists", "Patterns and Paradigms", "Algorithms and Applications",
    "Core Techniques", "Methods and Models", "A Practical Guide", "Case Studies",
    "Foundational Concepts", "A Comprehensive Survey", "Second Edition",
]

PUBLISHERS: List[str] = [
    "MIT Press", "Cambridge University Press", "Oxford University Press",
    "Springer International Publishing", "O'Reilly Media", "Addison-Wesley Professional",
    "Prentice Hall", "Academic Press", "Elsevier Science", "Morgan Kaufmann",
    "CRC Press", "Princeton University Press", "Harvard University Press",
]

# ── Study Spaces Vocabulary ───────────────────────────────────────────────────

ZONE_DEFINITIONS: List[Dict] = [
    {"zone_code": "ZONE-G-SILENT", "name": "Ground Floor Deep Focus Room", "floor": 0, "capacity": 25, "policy": "silent"},
    {"zone_code": "ZONE-1-COLLAB", "name": "1st Floor Commons & Collaborative Hub", "floor": 1, "capacity": 35, "policy": "collaborative"},
    {"zone_code": "ZONE-1-QUIET", "name": "1st Floor North Reading Terrace", "floor": 1, "capacity": 20, "policy": "quiet"},
    {"zone_code": "ZONE-2-TECH", "name": "2nd Floor Digital Innovation Lab", "floor": 2, "capacity": 25, "policy": "quiet"},
    {"zone_code": "ZONE-2-GRAD", "name": "2nd Floor Graduate Research Carrels", "floor": 2, "capacity": 15, "policy": "silent"},
    {"zone_code": "ZONE-3-SILENT", "name": "3rd Floor Tower Silent Study Wing", "floor": 3, "capacity": 15, "policy": "silent"},
    {"zone_code": "ZONE-3-MEDIA", "name": "3rd Floor Multimedia & Seminar Suite", "floor": 3, "capacity": 10, "policy": "collaborative"},
    {"zone_code": "ZONE-3-MATH", "name": "3rd Floor Mathematical Sciences Alcove", "floor": 3, "capacity": 5, "policy": "quiet"},
]

ROOM_DEFINITIONS: List[Dict] = [
    {"room_code": "ROOM-101", "name": "Seminar Suite Ada", "capacity": 10, "display": "projector", "whiteboard": True},
    {"room_code": "ROOM-102", "name": "Collaboration Pod Turing", "capacity": 6, "display": "tv", "whiteboard": True},
    {"room_code": "ROOM-103", "name": "Conference Room Hopper", "capacity": 12, "display": "dual_tv", "whiteboard": True},
    {"room_code": "ROOM-201", "name": "Study Studio Shannon", "capacity": 4, "display": "monitor", "whiteboard": True},
    {"room_code": "ROOM-202", "name": "Discussion Room Knuth", "capacity": 8, "display": "tv", "whiteboard": True},
    {"room_code": "ROOM-203", "name": "Seminar Room Dijkstra", "capacity": 6, "display": "tv", "whiteboard": False},
    {"room_code": "ROOM-204", "name": "Project Hub Liskov", "capacity": 8, "display": "tv", "whiteboard": True},
    {"room_code": "ROOM-301", "name": "Research Chamber von Neumann", "capacity": 14, "display": "projector", "whiteboard": True},
    {"room_code": "ROOM-302", "name": "Quiet Consultation Room Lamport", "capacity": 4, "display": "monitor", "whiteboard": True},
    {"room_code": "ROOM-303", "name": "Graduate Colloquium Goldwasser", "capacity": 16, "display": "dual_tv", "whiteboard": True},
]

# ── Telemetry & Search Vocabulary ─────────────────────────────────────────────

SEARCH_SAMPLE_QUERIES: List[str] = [
    "deep learning with python", "quantum algorithms", "distributed database systems",
    "operating systems concepts", "linear algebra done right", "introduction to algorithms",
    "graph neural networks", "reinforcement learning sutton", "cryptography and network security",
    "compiler construction aho", "convex optimization boyd", "stochastic calculus",
    "machine learning murphy", "computer vision algorithms", "natural language processing",
    "database management systems", "discrete mathematics and its applications", "design patterns",
    "clean architecture", "parallel programming cuda", "microservices patterns",
    "robotics mechanics and control", "bioinformatics algorithms", "information theory cover",
    "automata and computability", "quantum computing nielsen chuang", "probabilistic robotics",
    "pattern recognition and machine learning bishop", "foundations of data science",
    "computer networks tanenbaum", "artificial intelligence a modern approach",
]

INVENTORY_NOTES: List[str] = [
    "Annual RFID inventory verification; barcode scanned and RFID tag confirmed intact.",
    "Shelf location audit completed; spine label legible, RFID signal strong.",
    "Condition verified: excellent. Book copy placed on designated reserve stack.",
    "Minor cover wear noted during spot audit; barcode readable and structure solid.",
    "Routine physical inspection: pages intact, no highlighting or water marks.",
    "Binding audit: binding intact, spine firm, barcode rescanned successfully.",
    "Inventory sweep: copy located in designated call number sequence.",
    "Catalog sync check: physical item matches database shelf mark exactly.",
]

