from dupster.utils.formatting import human_size


def test_human_size_boundaries():
    assert human_size(0).startswith("0.0 B")
    assert human_size(1023).startswith("1023.0 B")
    assert human_size(1024).startswith("1.0 KB")
    assert human_size(1024 * 1024).startswith("1.0 MB")

