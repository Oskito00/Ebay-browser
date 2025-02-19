from datetime import datetime

def parse_date(date_str):
                if date_str:
                    try:
                        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except ValueError:
                        return None
                return None