from dupster.domain.models import DuplicateGroup


def test_potential_savings(tmp_path):
    f1 = tmp_path / "a.bin"; f1.write_bytes(b"x" * 10)
    f2 = tmp_path / "b.bin"; f2.write_bytes(b"y" * 6)
    g = DuplicateGroup(hash="h", files=[str(f1), str(f2)], index=1)
    assert g.potential_savings() == (10 + 6) - max(10, 6)

