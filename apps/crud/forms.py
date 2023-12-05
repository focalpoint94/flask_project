from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class UserForm(FlaskForm):
    username = StringField(
        "사용자명",
        validators=[
            DataRequired(message="사용자명은 필수입니다."),
            Length(max=30, message="최대 30 문자"),
        ],
    )

    email = StringField(
        "이메일",
        validators=[
            DataRequired(message="이메일은 필수입니다."),
            Email(message="메일 주소 형식 필요"),
        ],
    )

    password = PasswordField(
        "비밀번호",
        validators=[
            DataRequired(message="비밀번호는 필수입니다."),
        ]
    )

    submit = SubmitField("신규 등록")

