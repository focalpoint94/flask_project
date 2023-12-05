import random
import cv2
import torchvision.transforms.functional
from flask import current_app
from PIL import Image
from pathlib import Path
import torch
import numpy as np
import uuid

from apps.app import db
from apps.detector.models import UserImageTag


def make_color(labels):
    colors = [[random.randint(0, 255) for _ in range(3)] for _ in labels]
    color = random.choice(colors)
    return color


def make_line(result_image):
    line = round(0.002 * max(result_image.shape[0:2])) + 1
    return line


def draw_lines(c1, c2, result_image, line, color):
    # 사각형의 테두리 선을 이미지에 덧붙여 씀
    cv2.rectangle(result_image, c1, c2, color, thickness=line)
    return cv2


def draw_texts(result_image, line, c1, cv2, color, labels, label):
    # 감지한 텍스트 라벨을 이미지에 덧붙여 씀
    display_txt = f"{labels[label]}"
    font = max(line - 1, 1)
    t_size = cv2.getTextSize(display_txt, 0, fontScale=line / 3, thickness=font)[0]
    c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3
    cv2.rectangle(result_image, c1, c2, color, -1)
    cv2.putText(
        result_image,
        display_txt,
        (c1[0], c1[1] - 2),
        0,
        line / 3,
        [225, 255, 255],
        thickness=font,
        lineType=cv2.LINE_AA,
    )
    return cv2


def exec_detect(target_image_path):
    # 라벨 읽어 들이기
    labels = current_app.config["LABELS"]

    # 이미지 읽어 들이기
    image = Image.open(target_image_path)

    # 이미지 데이터를 텐서형의 수치 데이터로 변환
    image_tensor = torchvision.transforms.functional.to_tensor(image)

    # 학습 완료 모델의 읽어 들이기
    model = torch.load(Path(current_app.root_path, "detector", "model.pt"))

    # 모델의 추론 모드로 전환
    model = model.eval()

    # 추론의 실행
    output = model([image_tensor])[0]

    tags = []
    result_image = np.array(image.copy())
    # 학습 완료 모델이 감지한 각 물체만큼 이미지에 덧붙여 씀
    for box, label, score in zip(output["boxes"], output["labels"], output["scores"]):
        if score > 0.8 and labels[label] not in tags:
            current_app.logger.info(score)
            current_app.logger.info(labels[label])
            # 테두리 선의 색 결정
            color = make_color(labels)
            # 테두리 선의 작성
            line = make_line(result_image)
            # 감지 이미지의 테두리 선과 텍스트 라벨의 테두리 선의 위치 정보
            c1 = (int(box[0]), int(box[1]))
            c2 = (int(box[2]), int(box[3]))
            # 이미지에 테두리 선을 덧붙여 씀
            cv2 = draw_lines(c1, c2, result_image, line, color)
            # 이미지에 텍스트 라벨을 덧붙여 씀
            cv2 = draw_texts(result_image, line, c1, cv2, color, labels, label)
            tags.append(labels[label])

    # 감지 후의 이미지 파일명을 생성한다
    detected_image_file_name = str(uuid.uuid4()) + ".jpg"

    # 이미지 복사처 패스를 취득한다
    detected_image_file_path = str(
        Path(current_app.config["UPLOAD_FOLDER"], detected_image_file_name)
    )
    # 변환 후의 이미지 파일을 보존처로 복사한다
    cv2.imwrite(detected_image_file_path, cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR))
    return tags, detected_image_file_name


def save_detected_image_tags(user_image, tags, detected_image_file_name):
    # 감지 후 이미지의 보존처 패스를 DB에 보존한다
    user_image.image_path = detected_image_file_name
    # 감지 플래그를 True로 한다
    user_image.is_detected = True
    db.session.add(user_image)
    # user_images_tags 레코드를 작성한다
    for tag in tags:
        user_image_tag = UserImageTag(user_image_id=user_image.id, tag_name=tag)
        db.session.add(user_image_tag)
    db.session.commit()

