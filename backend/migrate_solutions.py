import os, json
from app import app
from models import db, Solution

def migrate_all_solutions():
    solutions_dir = os.path.join(os.path.dirname(__file__), 'solutions')
    imported = skipped = 0

    for filename in os.listdir(solutions_dir):
        if not filename.endswith('_solutions.json'):
            continue
        shape_id = filename[:-len('_solutions.json')]

        with open(os.path.join(solutions_dir, filename)) as f:
            for normalized in json.load(f):
                exists = Solution.query.filter_by(
                    user_id=None, shape_id=shape_id,
                    normalized_solution=normalized,
                ).first()
                if exists:
                    skipped += 1
                    continue
                db.session.add(Solution(shape_id=shape_id, normalized_solution=normalized))
                imported += 1

    db.session.commit()
    print(f"Imported {imported}, skipped {skipped} duplicates.")

if __name__ == '__main__':
    with app.app_context():
        migrate_all_solutions()