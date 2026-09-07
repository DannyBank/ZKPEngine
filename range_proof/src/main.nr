fn main(
	credit_score: u32,
	salary_range: u32,
	exam_score: u32,
	ucc_membership: str<11>
) {
    assert(
		(credit_score >= 80) &
		(salary_range <= 10000) &
		(exam_score >= 80) &
		(ucc_membership == "msite250020"))
}