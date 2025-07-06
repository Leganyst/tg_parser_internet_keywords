"""
Утилиты для мониторинга и логирования качества совпадений
"""

import json
import os
from datetime import datetime
from collections import defaultdict, Counter

class MatchQualityLogger:
    """Класс для логирования и анализа качества совпадений"""
    
    def __init__(self, log_file="match_quality.log"):
        self.log_file = log_file
        self.stats = {
            'total_matches': 0,
            'false_positives': 0,
            'true_positives': 0,
            'keyword_stats': defaultdict(int),
            'quality_distribution': Counter()
        }
    
    def log_match(self, original_text, matched_keyword, quality_metrics, is_false_positive=False):
        """Логируем совпадение с метриками качества"""
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'original_text': original_text,
            'matched_keyword': matched_keyword,
            'quality_metrics': quality_metrics,
            'is_false_positive': is_false_positive
        }
        
        # Записываем в файл
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        # Обновляем статистику
        self.update_stats(log_entry)
    
    def update_stats(self, log_entry):
        """Обновляем внутреннюю статистику"""
        self.stats['total_matches'] += 1
        
        if log_entry['is_false_positive']:
            self.stats['false_positives'] += 1
        else:
            self.stats['true_positives'] += 1
        
        self.stats['keyword_stats'][log_entry['matched_keyword']] += 1
        
        if log_entry['quality_metrics']:
            confidence = log_entry['quality_metrics'].get('confidence', 'unknown')
            self.stats['quality_distribution'][confidence] += 1
    
    def get_statistics(self):
        """Возвращает статистику по качеству совпадений"""
        total = self.stats['total_matches']
        if total == 0:
            return "Нет данных для анализа"
        
        accuracy = (self.stats['true_positives'] / total) * 100
        
        report = f"""
=== СТАТИСТИКА КАЧЕСТВА СОВПАДЕНИЙ ===

Общая точность: {accuracy:.1f}%
Всего совпадений: {total}
Правильных: {self.stats['true_positives']}
Ложных срабатываний: {self.stats['false_positives']}

Распределение по уверенности:
"""
        
        for confidence, count in self.stats['quality_distribution'].items():
            percentage = (count / total) * 100
            report += f"  {confidence}: {count} ({percentage:.1f}%)\n"
        
        report += "\nТоп-10 ключевых слов по частоте срабатывания:\n"
        for keyword, count in self.stats['keyword_stats'].most_common(10):
            percentage = (count / total) * 100
            report += f"  '{keyword}': {count} ({percentage:.1f}%)\n"
        
        return report
    
    def analyze_problematic_keywords(self):
        """Анализирует ключевые слова, которые часто дают ложные срабатывания"""
        
        if not os.path.exists(self.log_file):
            return "Лог-файл не найден"
        
        false_positive_keywords = Counter()
        total_keyword_matches = Counter()
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    keyword = entry['matched_keyword']
                    total_keyword_matches[keyword] += 1
                    
                    if entry['is_false_positive']:
                        false_positive_keywords[keyword] += 1
                except json.JSONDecodeError:
                    continue
        
        report = "\n=== АНАЛИЗ ПРОБЛЕМНЫХ КЛЮЧЕВЫХ СЛОВ ===\n"
        
        for keyword, false_count in false_positive_keywords.most_common(10):
            total_count = total_keyword_matches[keyword]
            false_rate = (false_count / total_count) * 100
            report += f"'{keyword}': {false_count}/{total_count} ложных ({false_rate:.1f}%)\n"
        
        return report

def create_quality_report(log_file="match_quality.log"):
    """Создает отчет о качестве совпадений"""
    
    logger = MatchQualityLogger(log_file)
    
    # Загружаем статистику из файла
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    logger.update_stats(entry)
                except json.JSONDecodeError:
                    continue
    
    report = logger.get_statistics()
    report += logger.analyze_problematic_keywords()
    
    return report

# Глобальный экземпляр логгера
quality_logger = MatchQualityLogger()
