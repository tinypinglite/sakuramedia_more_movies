from sakuramedia_more_movies.heat import calculate_heat, movie_heat


def test_zero_counts_gives_zero():
    assert calculate_heat() == 0


def test_reference_counts_gives_scale():
    assert (
        calculate_heat(
            watched_count=1308,
            want_watch_count=4991,
            comment_count=41,
            score_number=6291,
        )
        == 3100
    )


def test_rounding_matches_formula():
    expected = int(
        3100
        * (
            7 / 34 * 100 / 1308
            + 5 / 34 * 200 / 4991
            + 17 / 34 * 10 / 41
            + 5 / 34 * 300 / 6291
        )
        + 0.5
    )
    assert (
        calculate_heat(
            watched_count=100,
            want_watch_count=200,
            comment_count=10,
            score_number=300,
        )
        == expected
    )


def test_movie_heat_reads_detail_fields():
    class Detail:
        watched_count = 1308
        want_watch_count = 4991
        comment_count = 41
        score_number = 6291

    assert movie_heat(Detail()) == 3100


def test_movie_heat_tolerates_missing_fields():
    class Detail:
        pass

    assert movie_heat(Detail()) == 0
