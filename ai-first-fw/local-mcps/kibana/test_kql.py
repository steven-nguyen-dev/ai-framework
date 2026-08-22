#!/usr/bin/env python3
"""
Unit tests for the KQL -> Query DSL translator in kql.py.

Runs entirely offline: no Kibana, no network, no dependencies beyond the
standard library. Run it after any change to kql.py:

    python3 test_kql.py            # or: python3 -m unittest test_kql -v
"""

import unittest

from kql import KqlError, to_dsl


class TestBasics(unittest.TestCase):
    def test_blank_is_match_all(self):
        self.assertEqual(to_dsl(""), {"match_all": {}})
        self.assertEqual(to_dsl("   "), {"match_all": {}})
        self.assertEqual(to_dsl(None), {"match_all": {}})

    def test_field_term(self):
        self.assertEqual(to_dsl("log.level:ERROR"), {"match": {"log.level": "ERROR"}})

    def test_field_quoted_phrase(self):
        self.assertEqual(
            to_dsl('message:"connection reset by peer"'),
            {"match_phrase": {"message": "connection reset by peer"}},
        )

    def test_field_exists(self):
        self.assertEqual(to_dsl("error.stack_trace:*"), {"exists": {"field": "error.stack_trace"}})

    def test_field_wildcard(self):
        self.assertEqual(
            to_dsl("service.name:carrier-*"),
            {"query_string": {"fields": ["service.name"], "query": "carrier-*", "analyze_wildcard": True}},
        )

    def test_bare_term(self):
        self.assertEqual(to_dsl("NullPointerException"),
                         {"multi_match": {"query": "NullPointerException", "lenient": True}})

    def test_bare_phrase(self):
        self.assertEqual(to_dsl('"order sync failed"'),
                         {"multi_match": {"query": "order sync failed", "type": "phrase", "lenient": True}})

    def test_equals_is_treated_as_colon(self):
        self.assertEqual(to_dsl("log.level=ERROR"), to_dsl("log.level:ERROR"))


class TestBooleans(unittest.TestCase):
    def test_and(self):
        self.assertEqual(
            to_dsl("log.level:ERROR and service.name:oms"),
            {"bool": {"filter": [{"match": {"log.level": "ERROR"}}, {"match": {"service.name": "oms"}}]}},
        )

    def test_or(self):
        self.assertEqual(
            to_dsl("log.level:ERROR or log.level:WARN"),
            {"bool": {"should": [{"match": {"log.level": "ERROR"}}, {"match": {"log.level": "WARN"}}],
                      "minimum_should_match": 1}},
        )

    def test_not(self):
        self.assertEqual(
            to_dsl("not log.level:INFO"),
            {"bool": {"must_not": [{"match": {"log.level": "INFO"}}]}},
        )

    def test_case_insensitive_operators(self):
        self.assertEqual(to_dsl("a:1 AND b:2"), to_dsl("a:1 and b:2"))
        self.assertEqual(to_dsl("a:1 OR b:2"), to_dsl("a:1 or b:2"))
        self.assertEqual(to_dsl("NOT a:1"), to_dsl("not a:1"))

    def test_implicit_and(self):
        self.assertEqual(to_dsl("a:1 b:2"), to_dsl("a:1 and b:2"))

    def test_or_binds_looser_than_and(self):
        # a AND b OR c  ==  (a AND b) OR c
        self.assertEqual(to_dsl("a:1 and b:2 or c:3"), to_dsl("(a:1 and b:2) or c:3"))

    def test_grouping_overrides_precedence(self):
        self.assertEqual(
            to_dsl("a:1 and (b:2 or c:3)"),
            {"bool": {"filter": [
                {"match": {"a": "1"}},
                {"bool": {"should": [{"match": {"b": "2"}}, {"match": {"c": "3"}}],
                          "minimum_should_match": 1}},
            ]}},
        )

    def test_field_value_list(self):
        self.assertEqual(
            to_dsl("service.name:(oms or wms or pms)"),
            {"bool": {"should": [
                {"match": {"service.name": "oms"}},
                {"match": {"service.name": "wms"}},
                {"match": {"service.name": "pms"}},
            ], "minimum_should_match": 1}},
        )

    def test_field_value_list_with_not(self):
        self.assertEqual(
            to_dsl("log.level:(ERROR and not INFO)"),
            {"bool": {"filter": [
                {"match": {"log.level": "ERROR"}},
                {"bool": {"must_not": [{"match": {"log.level": "INFO"}}]}},
            ]}},
        )

    def test_negated_field_value(self):
        self.assertEqual(
            to_dsl("service.name:not oms"),
            {"bool": {"must_not": [{"match": {"service.name": "oms"}}]}},
        )


class TestRanges(unittest.TestCase):
    def test_numeric_coercion(self):
        self.assertEqual(to_dsl("status >= 500"),
                         {"range": {"status": {"gte": 500}}})
        self.assertEqual(to_dsl("latency > 1.5"),
                         {"range": {"latency": {"gt": 1.5}}})

    def test_all_operators(self):
        self.assertEqual(to_dsl("a < 1"), {"range": {"a": {"lt": 1}}})
        self.assertEqual(to_dsl("a <= 1"), {"range": {"a": {"lte": 1}}})
        self.assertEqual(to_dsl("a > 1"), {"range": {"a": {"gt": 1}}})
        self.assertEqual(to_dsl("a >= 1"), {"range": {"a": {"gte": 1}}})

    def test_date_stays_a_string(self):
        self.assertEqual(
            to_dsl('@timestamp >= "2026-08-01T00:00:00Z"'),
            {"range": {"@timestamp": {"gte": "2026-08-01T00:00:00Z"}}},
        )

    def test_range_combines_with_boolean(self):
        self.assertEqual(
            to_dsl("status >= 500 and service.name:oms"),
            {"bool": {"filter": [
                {"range": {"status": {"gte": 500}}},
                {"match": {"service.name": "oms"}},
            ]}},
        )


class TestEscaping(unittest.TestCase):
    def test_escaped_quote_inside_phrase(self):
        self.assertEqual(to_dsl(r'message:"he said \"hi\""'),
                         {"match_phrase": {"message": 'he said "hi"'}})

    def test_escaped_colon_in_bare_word(self):
        self.assertEqual(to_dsl(r"message:foo\:bar"),
                         {"match": {"message": "foo:bar"}})

    def test_words_that_merely_contain_keywords(self):
        # 'android' starts with 'and' but is not the operator
        self.assertEqual(to_dsl("os:android"), {"match": {"os": "android"}})

    def test_dashes_and_dots_in_values(self):
        self.assertEqual(to_dsl("host.name:apac-elk-node-01.anchanto.com"),
                         {"match": {"host.name": "apac-elk-node-01.anchanto.com"}})


class TestErrors(unittest.TestCase):
    def _bad(self, text):
        with self.assertRaises(KqlError):
            to_dsl(text)

    def test_unterminated_quote(self):
        self._bad('message:"never closed')

    def test_dangling_colon(self):
        self._bad("log.level:")

    def test_unbalanced_paren(self):
        self._bad("(a:1 and b:2")

    def test_trailing_operator(self):
        self._bad("a:1 and")

    def test_stray_close_paren(self):
        self._bad("a:1)")

    def test_quoted_field_name(self):
        self._bad('"log.level":ERROR')


class TestRealisticQueries(unittest.TestCase):
    def test_kitchen_sink_parses(self):
        dsl = to_dsl(
            'log.level:ERROR and service.name:(oms or wms) '
            'and not message:"health check" and http.response.status_code >= 500'
        )
        self.assertEqual(len(dsl["bool"]["filter"]), 4)

    def test_deeply_nested(self):
        dsl = to_dsl("((a:1 or b:2) and (c:3 or (d:4 and not e:5)))")
        self.assertIn("bool", dsl)


if __name__ == "__main__":
    unittest.main(verbosity=2)
