from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class UserProfile(BaseModel):
    userId: Optional[str] = None
    accountName: Optional[str] = None
    name: Optional[str] = None
    placeId: Optional[int] = None
    placeName: Optional[str] = None
    birth: Optional[str] = None
    studentNum: Optional[str] = None
    isMfa: Optional[bool] = False

class AccessCodeItem(BaseModel):
    schoolId: Optional[str] = None
    schoolName: Optional[str] = None
    issueFiscalYear: Optional[str] = None
    expiresAt: Optional[str] = None
    classId: Optional[int] = None
    className: Optional[str] = None

class UserInfo(BaseModel):
    userType: Optional[int] = 8
    userInfo: Optional[UserProfile] = None
    accessCodes: List[AccessCodeItem] = Field(default_factory=list)

class Option(BaseModel):
    id: int
    text: str

class Question(BaseModel):
    id: int
    text: str
    audioUrl: Optional[str] = None
    imageUrl: Optional[str] = None
    questionNum: Optional[int] = None
    questionSource: Optional[str] = None
    answerCount: Optional[int] = 1
    options: List[Option] = Field(default_factory=list)
    answers: Optional[List[Option]] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.options and self.answers:
            self.options = self.answers

class MainQuestion(BaseModel):
    id: int
    text: str
    audioUrl: Optional[str] = None
    imageUrl: Optional[str] = None
    type: int = 0
    questions: List[Question] = Field(default_factory=list)

class TestQuestionSet(BaseModel):
    __test__ = False
    id: int
    title: str
    bookName: str
    count: int
    mainQuestions: List[MainQuestion] = Field(default_factory=list)

class TestItem(BaseModel):
    __test__ = False
    distributionId: int
    title: str
    bookName: str
    limitTime: Optional[int] = None
    questionCount: Optional[int] = None
    correctCount: Optional[int] = None
    status: Optional[int] = None  # 1: 未受験, 3: 完了, etc.
    startAt: Optional[str] = None
    endAt: Optional[str] = None
    answerAt: Optional[str] = None

class AnswerResult(BaseModel):
    id: int
    order: int = 0

class QuestionAnswer(BaseModel):
    testQuestionId: int
    results: List[AnswerResult]

class SubmittedPayload(BaseModel):
    distributionId: int
    testAnswers: List[QuestionAnswer]
