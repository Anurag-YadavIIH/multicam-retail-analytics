"""scripts/calibrate_reid.py tests. Only compute_report is pure/worth unit
testing here - extract()/calibrate() touch the filesystem, a real video and
a real model, and are exercised manually (see the script's own docstring)."""

from scripts.calibrate_reid import UNLABELED, compute_report, cosine_similarity


def test_cosine_similarity_identical_vectors_is_one():
    assert abs(cosine_similarity([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_cosine_similarity_zero_vector_is_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_compute_report_excludes_unlabeled_tracks():
    embeddings = {"1": [1.0, 0.0], "2": [1.0, 0.0], "3": [0.0, 1.0]}
    labels = {"1": "person_a", "2": "person_a", "3": UNLABELED}

    report = compute_report(embeddings, labels)

    assert report["same_person"] == [1.0]
    assert report["different_person"] == []


def test_compute_report_clean_separation_recommends_midpoint():
    embeddings = {
        "1": [1.0, 0.0],
        "2": [0.99, 0.01],
        "3": [0.0, 1.0],
    }
    labels = {"1": "person_a", "2": "person_a", "3": "person_b"}

    report = compute_report(embeddings, labels)

    assert report["clean_separation"] is True
    lowest_same = min(report["same_person"])
    highest_diff = max(report["different_person"])
    assert report["recommended_threshold"] == round((lowest_same + highest_diff) / 2, 2)


def test_compute_report_no_separation_when_overlapping():
    embeddings = {
        "1": [1.0, 0.0],
        "2": [0.5, 0.5],
        "3": [0.0, 1.0],
        "4": [0.5, 0.5],
    }
    labels = {"1": "person_a", "2": "person_a", "3": "person_b", "4": "person_b"}

    report = compute_report(embeddings, labels)

    assert report["clean_separation"] is False
    assert report["recommended_threshold"] is None


def test_compute_report_empty_without_enough_labels():
    report = compute_report({"1": [1.0, 0.0]}, {"1": "person_a"})

    assert report["same_person"] == []
    assert report["different_person"] == []
    assert report["recommended_threshold"] is None
