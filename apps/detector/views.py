from apps.app import db
from apps.crud.models import User
from apps.detector.models import UserImage, UserImageTag
import uuid
from pathlib import Path
from apps.detector.forms import UploadImageForm, DetectorForm, DeleteForm
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
    request,
)
from flask_login import current_user, login_required
from apps.detector.utils import exec_detect, save_detected_image_tags
from sqlalchemy.exc import SQLAlchemyError


dt = Blueprint(
    "detector",
    __name__,
    template_folder="templates"
)


@dt.route("/")
def index():
    user_images = (
        db.session.query(User, UserImage)
        .join(UserImage)
        .filter(User.id == UserImage.user_id)
        .all()
    )
    # 태그 일람을 취득한다
    user_image_tag_dict = {}
    for user_image in user_images:
        # 이미지에 연결된 태그 일람을 취득한다
        user_image_tags = (
            db.session.query(UserImageTag)
                .filter(UserImageTag.user_image_id == user_image.UserImage.id)
                .all()
        )
        user_image_tag_dict[user_image.UserImage.id] = user_image_tags
    # 물체 검지 폼을 인스턴스화한다
    detector_form = DetectorForm()
    delete_form = DeleteForm()
    return render_template(
        "detector/index.html",
        user_images=user_images,
        # 태그 일람을 템플릿에 건넨다
        user_image_tag_dict=user_image_tag_dict,
        # 물체 검지 폼을 템플릿에 건넨다
        detector_form=detector_form,
        delete_form=delete_form,
    )


@dt.route("/images/<path:filename>")
def image_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@dt.route("/upload", methods=["GET", "POST"])
@login_required
def upload_image():
    form = UploadImageForm()
    if form.validate_on_submit():
        file = form.image.data
        ext = Path(file.filename).suffix
        image_uuid_file_name = str(uuid.uuid4()) + ext
        image_path = Path(current_app.config["UPLOAD_FOLDER"], image_uuid_file_name)
        file.save(image_path)
        user_image = UserImage(user_id=current_user.id, image_path=image_uuid_file_name)
        db.session.add(user_image)
        db.session.commit()
        return redirect(url_for("detector.index"))
    return render_template("detector/upload.html", form=form)


@dt.route("/detect/<string:image_id>", methods=["POST"])
@login_required
def detect(image_id):
    user_image = db.session.query(UserImage).filter(UserImage.id == image_id).first()
    if user_image is None:
        flash("no such image exists")
        return redirect(url_for("detector.index"))

    target_image_path = Path(current_app.config["UPLOAD_FOLDER"], user_image.image_path)

    tags, detected_image_file_name = exec_detect(target_image_path)
    try:
        save_detected_image_tags(user_image, tags, detected_image_file_name)
    except SQLAlchemyError as e:
        flash("An error occurred during detection")
        db.session.rollback()
        current_app.logger.error(e)
        return redirect(url_for("detector.index"))
    return redirect(url_for("detector.index"))


@dt.route("/images/delete/<string:image_id>", methods=["POST"])
@login_required
def delete_image(image_id):
    try:
        # user_image_tags 테이블로부터 레코드를 삭제한다
        db.session.query(UserImageTag).filter(
            UserImageTag.user_image_id == image_id
        ).delete()

        # user_images 테이블로부터 레코드를 삭제한다
        db.session.query(UserImage).filter(UserImage.id == image_id).delete()

        db.session.commit()
    except Exception as e:
        flash("이미지 삭제 처리에서 오류가 발생했습니다.")
        # 오류 로그 출력
        current_app.logger.error(e)
        db.session.rollback()
    return redirect(url_for("detector.index"))


@dt.route("/images/search", methods=["GET"])
def search():
    # 이미지 일람을 취득한다
    user_images = db.session.query(User, UserImage).join(
        UserImage, User.id == UserImage.user_id
    )

    # GET 파라미터로부터 검색 워드를 취득한다
    search_text = request.args.get("search")

    user_image_tag_dict = {}
    filtered_user_images = []

    # user_images를 루프하여 user_images에 연결된 정보를 검색한다
    for user_image in user_images:
        # 검색 워드가 빈 경우는 모든 태그를 취득한다
        if not search_text:
            # 태그 일람을 취득한다
            user_image_tags = (
                db.session.query(UserImageTag)
                .filter(UserImageTag.user_image_id == user_image.UserImage.id)
                .all()
            )
        else:
            # 검색 워드로 추출한 태그를 취득한다
            user_image_tags = (
                db.session.query(UserImageTag)
                .filter(UserImageTag.user_image_id == user_image.UserImage.id)
                .filter(UserImageTag.tag_name.like("%" + search_text + "%"))
                .all()
            )

            # 태그를 찾을 수 없었다면 이미지를 반환하지 않는다
            if not user_image_tags:
                continue

            # 태그가 있는 경우는 태그 정보를 다시 취득한다
            user_image_tags = (
                db.session.query(UserImageTag)
                .filter(UserImageTag.user_image_id == user_image.UserImage.id)
                .all()
            )

        # user_image_id를 키로 하는 사전에 태그 정보를 세트한다
        user_image_tag_dict[user_image.UserImage.id] = user_image_tags

        # 추출 결과의 user_image 정보를 배열 세트한다
        filtered_user_images.append(user_image)

    delete_form = DeleteForm()
    detector_form = DetectorForm()

    return render_template(
        "detector/index.html",
        # 추출한 user_images 배열을 건넨다
        user_images=filtered_user_images,
        # 이미지에 연결된 태그 일람의 사전을 건넨다
        user_image_tag_dict=user_image_tag_dict,
        delete_form=delete_form,
        detector_form=detector_form,
    )


@dt.errorhandler(404)
def page_not_found(e):
    return render_template("detector/404.html"), 404

