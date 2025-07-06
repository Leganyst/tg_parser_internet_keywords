import json
import os
from datetime import datetime
from collections import Counter

class MatchQualityLogger:
    def __init__(self, log_file="match_quality.log"):
        self.log_file = log_file

    def log_match(self, original_text, matched_keyword, quality_metrics, is_false_positive=False):
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'original_text': original_text,
            'matched_keyword': matched_keyword,
            'quality_metrics': quality_metrics,
            'is_false_positive': is_false_positive
        }
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def get_statistics(self):
        if not os.path.exists(self.log_file):
            return "Нет данных для анализа"
        total_matches = 0
        false_positives = 0
        keyword_stats = Counter()
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    total_matches += 1
                    if entry.get('is_false_positive'):
                        false_positives += 1
                    keyword_stats[entry['matched_keyword']] += 1
                except json.JSONDecodeError:
                    continue
        if total_matches == 0:
            return "Нет данных для анализа"
        accuracy = ((total_matches - false_positives) / total_matches) * 100
        report = f"=== СТАТИСТИКА КАЧЕСТВА ===\n\nТочность: {accuracy:.1f}%\nВсего: {total_matches}\nЛожных: {false_positives}\n\nТоп-5 ключевых слов:\n"
        for keyword, count in keyword_stats.most_common(5):
            percentage = (count / total_matches) * 100
            report += f"  '{keyword}': {count} ({percentage:.1f}%)\n"
        return report

quality_logger = MatchQualityLogger()

def create_quality_report(log_file="match_quality.log"):
    """Создает отчет о качестве"""
    logger = MatchQualityLogger(log_file)
    return logger.get_statistics()
