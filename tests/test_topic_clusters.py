"""Topic discovery regression tests; no external APIs required."""
import unittest

from topic_clusters import cluster_topics


def link(uid, caption="", folders=None):
    return {"id":uid,"url":"https://example.org/"+uid,"captions":[caption] if caption else [],
            "folders":folders or []}


class ClusterTests(unittest.TestCase):
    def test_no_unfounded_topics_from_bare_reel_urls(self):
        links=[link("one"),link("two"),link("three")]
        self.assertEqual([],cluster_topics(links,[]))

    def test_unique_links_and_overlap(self):
        links=[
            link("one","#Python #Coding Python development"),
            link("two","#Coding #Python Python projects"),
            link("three","#Python #AI Python tips"),
            link("four","#AI #Python Python tools"),
        ]
        clusters=cluster_topics(links,[])
        python_topic=next(c for c in clusters if c["type"]=="hashtag" and
                          any(t["term"]=="python" for t in c["hashtags"]))
        self.assertEqual(4,python_topic["count"])
        self.assertEqual(4,len(set(python_topic["link_ids"])))
        self.assertGreaterEqual(len(clusters),1)

    def test_existing_nested_folder_creates_topic(self):
        folders=[{"id":5,"name":"Python","path":"groups/Programmieren/Python"},
                 {"id":6,"name":"Random","path":"misc/Random"}]
        links=[link("a",folders=[5]),link("b",folders=[5]),link("c",folders=[6])]
        groups=cluster_topics(links,folders)
        self.assertEqual("Python",groups[0]["title"])
        self.assertEqual("group",groups[0]["type"])
        self.assertEqual([5],groups[0]["folder_ids"])
        self.assertEqual(2,groups[0]["count"])

    def test_keywords_with_three_distinct_links_form_topic(self):
        links=[
            link("a","Painting landscapes"),
            link("b","Painting portraits"),
            link("c","Painting sunsets")
        ]
        result=cluster_topics(links,[])
        self.assertTrue(any(c["type"]=="keyword" and c["title"]=="painting" for c in result))

    def test_reproducible_order_and_ids(self):
        links=[link("a","#design sketches"),link("b","#design ideas"),
               link("c","#gaming stream"),link("d","#gaming guide")]
        a=cluster_topics(links,[])
        b=cluster_topics(list(reversed(links)),[])
        self.assertEqual(a,b)

    def test_single_link_or_duplicated_caption_does_not_form_topic(self):
        links=[link("a","#unique #unique #unique")]
        self.assertEqual([],cluster_topics(links,[]))


if __name__ == "__main__":
    unittest.main()
