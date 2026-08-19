from pydantic import BaseModel, Field


class CourseFeedbackRequest(BaseModel):
    course_id: int = Field(..., gt=0, description="선택한 추천 코스의 DB ID")
