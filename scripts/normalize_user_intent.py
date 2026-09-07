import argparse
import json
import os
import sys

from create_session import (
    SessionStateValidationError,
    load_state_from_path,
    resolve_workspace_root,
    state_file_path,
    validate_session_id,
)


class IntentNormalizationError(Exception):
    pass


CONTINUE_KEYWORDS = ["继续", "接着", "往下", "恢复", "上次", "继续任务", "继续做", "接着做", "go on", "resume"]
STATUS_KEYWORDS = ["状态", "进度", "到哪", "到哪一步", "当前阶段", "status"]
APPROVE_KEYWORDS = ["通过", "确认", "没问题", "可以", "同意", "进入设计", "进入系统设计", "进入 UI 设计", "进入ui设计"]
START_KEYWORDS = ["执行", "开始开发", "开始并行", "开始编码", "跑起来", "开始任务"]
EXECUTION_SUMMARY_APPROVE_KEYWORDS = ["按此执行", "执行摘要通过", "摘要没问题", "确认执行摘要", "按摘要执行"]
EXECUTION_SUMMARY_REVISION_KEYWORDS = ["执行摘要未通过", "摘要不通过", "摘要不对", "执行风险不接受"]
ALIGNMENT_APPROVE_KEYWORDS = ["需求校对通过", "完成交付", "可以交付", "交付吧", "校对通过"]
ALIGNMENT_REVISION_KEYWORDS = ["需求校对未通过", "校对不通过", "需求没满足", "返回修正", "验收不通过"]
CODE_REVIEW_REVISION_KEYWORDS = ["代码审查未通过", "代码评审未通过", "审查未通过", "审查不通过", "code review未通过", "review不通过"]
TEST_REVISION_KEYWORDS = ["测试未通过", "测试不通过", "测试失败", "集成测试未通过", "test fail", "test failed"]
APPLY_RETRY_KEYWORDS = ["应用冲突已处理", "冲突已处理", "重新应用", "重试应用", "apply retry"]
PRD_DECISION_CONFIRM_KEYWORDS = ["已确认", "决策确认", "确认完成", "重新生成prd", "重新生成 prd"]
PRD_REVISION_KEYWORDS = ["prd不", "prd 不", "prd有问题", "prd 有问题", "需求不", "重新生成", "重新分析", "补充需求", "追加需求", "漏了", "少了", "改prd", "改 prd", "需求要改"]
DESIGN_REVISION_KEYWORDS = ["设计不", "设计有问题", "重新设计", "架构不", "接口设计不", "数据库设计不", "模块划分不", "design不", "design 不"]
UI_REVISION_KEYWORDS = ["ui不", "ui 不", "ui有问题", "ui 有问题", "界面不", "页面不", "交互不", "视觉不", "预览不", "原型不", "颜色不", "字体不", "图标不", "导航不", "搜索不", "页面跳转不", "重新设计ui", "重新设计 ui"]
UI_APPROVE_KEYWORDS = ["ui通过", "ui 通过", "界面通过", "页面通过", "预览通过", "原型通过", "进入系统设计"]
IMPACT_KEYWORDS = ["需求变", "需求变化", "设计变", "设计变化", "影响分析", "需求要改", "设计要改", "模块要改", "接口要改", "测试后发现", "校对发现", "prd要调整", "prd 要调整"]
AMBIGUOUS_KEYWORDS = ["不行", "不对", "有问题", "改一下", "调整一下", "重新来", "不是我要的"]
LOCAL_RERUN_APPROVE_KEYWORDS = ["局部重跑", "按影响分析继续", "影响分析通过", "同意局部", "继续重跑"]
MANUAL_HANDLE_KEYWORDS = ["人工处理", "不要自动", "先停", "不通过"]
INITIALIZATION_OPTIONS = {
    "java": ["jdk-8", "jdk-11", "jdk-17"],
    "go": ["go-1.25"],
    "springboot": ["springboot-2.x", "springboot-3.x"],
    "pom": ["maven-3.5.x", "maven-3.9.x"],
    "lua": ["lua-4.x", "lua-5.x"],
}
INITIALIZATION_CATEGORY_ALIASES = {
    "java": ["java", "jdk"],
    "go": ["go", "golang"],
    "springboot": ["springboot", "spring-boot", "spring_boot"],
    "pom": ["pom", "maven"],
    "lua": ["lua"],
}
INITIALIZATION_VERSION_ALIASES = {
    "jdk-8": ["jdk-8", "jdk8", "jdk1.8", "java8", "java1.8"],
    "jdk-11": ["jdk-11", "jdk11", "java11"],
    "jdk-17": ["jdk-17", "jdk17", "java17"],
    "go-1.25": ["go-1.25", "go1.25", "golang1.25"],
    "springboot-2.x": ["springboot-2.x", "springboot2", "springboot2.x", "springboot-2", "springboot 2", "spring boot 2"],
    "springboot-3.x": ["springboot-3.x", "springboot3", "springboot3.x", "springboot-3", "springboot 3", "spring boot 3"],
    "maven-3.5.x": ["maven-3.5.x", "maven3.5", "maven3.5.x", "pom3.5", "pom 3.5"],
    "maven-3.9.x": ["maven-3.9.x", "maven3.9", "maven3.9.x", "pom3.9", "pom 3.9"],
    "lua-4.x": ["lua-4.x", "lua4", "lua4.x", "lua-4", "lua 4"],
    "lua-5.x": ["lua-5.x", "lua5", "lua5.x", "lua-5", "lua 5"],
}


CANONICAL_REPLIES = {
    "prd_decisions_confirmed": "已确认，重新生成 PRD",
    "prd_revision_requested": "PRD未通过，按反馈重新分析",
    "design_revision_requested": "设计未通过，按反馈重新设计",
    "ui_revision_requested": "UI设计未通过，按反馈重新设计",
    "approve_ui_and_proceed": "UI设计通过，进入系统设计",
    "select_project_category": "选择初始化项目分类",
    "select_project_version": "选择初始化项目版本",
    "change_impact_requested": "需求变更，执行影响分析",
    "continue_current_flow": "继续任务",
    "approve_and_proceed": "通过，进入 UI 设计",
    "execution_summary_approved": "按此执行",
    "execution_summary_revision_requested": "执行摘要未通过，返回修正",
    "start_execution": "执行",
    "requirement_alignment_approved": "需求校对通过，完成交付",
    "requirement_alignment_revision_requested": "需求校对未通过，返回修正",
    "code_review_revision_requested": "代码审查未通过，返回修正",
    "test_revision_requested": "测试未通过，返回修正",
    "apply_retry_requested": "应用冲突已处理，重新应用",
    "local_rerun_approved": "影响分析通过，执行局部重跑",
    "manual_handling_requested": "影响分析不通过，人工处理",
    "show_status": "查看状态",
    "choose_from_options": "请选择下一步动作",
    "unknown": "无法识别用户意图",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Normalize free-form user input to a SUPERLOOPER canonical action.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--session-id", required=True, help="执行会话 ID。")
    parser.add_argument("--user-input", required=True, help="用户自然语言输入。")
    return parser.parse_args()


def normalize_text(value):
    return str(value or "").strip().lower().replace(" ", "")


def contains_any(normalized, keywords):
    return any(normalize_text(keyword) in normalized for keyword in keywords)


def initialization_category_from_input(value):
    normalized = normalize_text(value)
    for category, aliases in INITIALIZATION_CATEGORY_ALIASES.items():
        if normalized in {normalize_text(alias) for alias in aliases}:
            return category
    return None


def initialization_version_from_input(value):
    normalized = normalize_text(value)
    for version, aliases in INITIALIZATION_VERSION_ALIASES.items():
        if normalized in {normalize_text(alias) for alias in aliases}:
            return version
    return None


def result(action, confidence, feedback, requires_choice, choice_options, reason):
    return {
        "canonical_action": action,
        "canonical_reply": CANONICAL_REPLIES[action],
        "confidence": confidence,
        "feedback": feedback,
        "requires_choice": requires_choice,
        "choice_options": choice_options,
        "reason": reason,
    }


def choice(feedback, options, reason):
    return result("choose_from_options", "low", feedback, True, options, reason)


def normalize_user_intent(state, user_input):
    feedback = str(user_input or "").strip()
    if not feedback:
        return choice(feedback, ["show_status", "continue_current_flow"], "用户输入为空。")
    normalized = normalize_text(feedback)
    current_phase = state.get("current_phase")
    phase_status = state.get("phase_status")
    project_initialized = state.get("project_initialized") is True

    if state.get("current_phase") == "report" and state.get("phase_status") == "passed":
        return result("show_status", "high", feedback, False, [], "session 已完成，只返回状态。")

    if contains_any(normalized, STATUS_KEYWORDS):
        return result("show_status", "high", feedback, False, [], "用户请求查看当前状态。")

    if current_phase == "requirement_alignment" and phase_status == "waiting_review" and contains_any(normalized, ALIGNMENT_REVISION_KEYWORDS):
        return result("requirement_alignment_revision_requested", "high", feedback, False, [], "用户确认需求反向校对未通过，需要进入受控修正。")

    if contains_any(normalized, LOCAL_RERUN_APPROVE_KEYWORDS) and state.get("change_impact_report"):
        return result("local_rerun_approved", "high", feedback, False, [], "用户确认按影响分析执行局部重跑。")

    if contains_any(normalized, MANUAL_HANDLE_KEYWORDS) and state.get("change_impact_report"):
        return result("manual_handling_requested", "high", feedback, False, [], "用户要求停止自动执行并人工处理。")

    if contains_any(normalized, CONTINUE_KEYWORDS):
        return result("continue_current_flow", "high", feedback, False, [], "用户要求沿当前 active session 继续。")

    if current_phase == "prd" and phase_status == "blocked":
        if contains_any(normalized, PRD_DECISION_CONFIRM_KEYWORDS):
            return result("prd_decisions_confirmed", "high", feedback, False, [], "PRD 阻塞决策已确认，重新调用 analyst 生成 PRD。")
        if contains_any(normalized, AMBIGUOUS_KEYWORDS):
            return choice(feedback, ["prd_decisions_confirmed", "show_status"], "PRD 阻塞阶段输入存在歧义。")

    if current_phase == "initialization" and phase_status == "waiting_review":
        category = initialization_category_from_input(feedback)
        if category:
            return result("select_project_category", "high", feedback, False, [], "用户选择初始化项目分类。")
        version = initialization_version_from_input(feedback)
        project_category = state.get("project_category")
        if version and project_category and version in INITIALIZATION_OPTIONS.get(project_category, []):
            return result("select_project_version", "high", feedback, False, [], "用户选择初始化项目版本。")
        if project_category:
            return choice(feedback, [*INITIALIZATION_OPTIONS.get(project_category, []), *INITIALIZATION_OPTIONS.keys()], "初始化阶段输入不是当前分类允许的版本。")
        return choice(feedback, list(INITIALIZATION_OPTIONS.keys()), "初始化阶段需要先选择项目分类。")

    if current_phase == "prd" and phase_status == "waiting_review":
        if contains_any(normalized, PRD_REVISION_KEYWORDS):
            return result("prd_revision_requested", "high", feedback, False, [], "PRD 审核阶段用户要求修订 PRD。")
        if contains_any(normalized, APPROVE_KEYWORDS):
            return result("approve_and_proceed", "high", feedback, False, [], "PRD 审核阶段用户确认进入 UI 设计。")
        if contains_any(normalized, AMBIGUOUS_KEYWORDS):
            return choice(feedback, ["prd_revision_requested", "approve_and_proceed", "show_status"], "PRD 审核阶段输入存在歧义。")

    if current_phase == "ui_design" and phase_status == "waiting_review":
        if contains_any(normalized, PRD_REVISION_KEYWORDS + IMPACT_KEYWORDS):
            return result("prd_revision_requested", "high", feedback, False, [], "UI 审核阶段用户提出需求本身变化，返回 PRD 修订。")
        if contains_any(normalized, UI_REVISION_KEYWORDS):
            return result("ui_revision_requested", "high", feedback, False, [], "UI 审核阶段用户要求重新设计 UI。")
        if contains_any(normalized, UI_APPROVE_KEYWORDS) or contains_any(normalized, APPROVE_KEYWORDS):
            return result("approve_ui_and_proceed", "high", feedback, False, [], "UI 审核阶段用户确认进入系统设计。")
        if contains_any(normalized, AMBIGUOUS_KEYWORDS):
            return choice(feedback, ["ui_revision_requested", "approve_ui_and_proceed", "prd_revision_requested", "show_status"], "UI 审核阶段输入存在歧义。")

    if current_phase == "design" and phase_status == "waiting_review":
        if contains_any(normalized, IMPACT_KEYWORDS) and project_initialized:
            return result("change_impact_requested", "high", feedback, False, [], "设计已初始化后用户提出变更，需影响分析。")
        if contains_any(normalized, DESIGN_REVISION_KEYWORDS) and not project_initialized:
            return result("design_revision_requested", "high", feedback, False, [], "设计审核阶段用户要求重新设计。")
        if contains_any(normalized, DESIGN_REVISION_KEYWORDS) and project_initialized:
            return result("change_impact_requested", "high", feedback, False, [], "设计已初始化，设计变更需进入影响分析。")
        if "生成执行清单" in feedback or "执行清单" in feedback:
            return result("continue_current_flow", "high", feedback, False, [], "用户要求继续到执行清单。")
        if contains_any(normalized, APPROVE_KEYWORDS):
            return result("continue_current_flow", "high", feedback, False, [], "设计审核阶段用户确认继续。")
        if contains_any(normalized, AMBIGUOUS_KEYWORDS):
            options = ["change_impact_requested", "show_status"] if project_initialized else ["design_revision_requested", "continue_current_flow", "show_status"]
            return choice(feedback, options, "设计审核阶段输入存在歧义。")

    if current_phase == "requirement_alignment" and phase_status == "waiting_review":
        if contains_any(normalized, ALIGNMENT_REVISION_KEYWORDS):
            return result("requirement_alignment_revision_requested", "high", feedback, False, [], "用户确认需求反向校对未通过，需要进入受控修正。")
        if contains_any(normalized, ALIGNMENT_APPROVE_KEYWORDS):
            return result("requirement_alignment_approved", "high", feedback, False, [], "用户确认需求校对通过。")
        if contains_any(normalized, AMBIGUOUS_KEYWORDS):
            return choice(feedback, ["requirement_alignment_revision_requested", "requirement_alignment_approved", "show_status"], "需求反向校对阶段输入存在歧义。")

    if current_phase == "run" and phase_status == "waiting_review" and state.get("execution_summary_status") == "READY_FOR_APPROVAL":
        if contains_any(normalized, EXECUTION_SUMMARY_REVISION_KEYWORDS):
            return result("execution_summary_revision_requested", "high", feedback, False, [], "用户确认执行摘要未通过，需要返回修正。")
        if contains_any(normalized, EXECUTION_SUMMARY_APPROVE_KEYWORDS) or contains_any(normalized, START_KEYWORDS):
            return result("execution_summary_approved", "high", feedback, False, [], "用户确认执行摘要通过，允许进入并行开发。")
        if contains_any(normalized, AMBIGUOUS_KEYWORDS):
            return choice(feedback, ["execution_summary_approved", "execution_summary_revision_requested", "show_status"], "执行摘要审核阶段输入存在歧义。")

    if current_phase == "run":
        if contains_any(normalized, CODE_REVIEW_REVISION_KEYWORDS):
            return result("code_review_revision_requested", "high", feedback, False, [], "用户确认代码审查未通过，需要回到模块修正。")
        if contains_any(normalized, TEST_REVISION_KEYWORDS):
            return result("test_revision_requested", "high", feedback, False, [], "用户确认测试未通过，需要回到模块修正并重新测试。")
        if contains_any(normalized, APPLY_RETRY_KEYWORDS):
            return result("apply_retry_requested", "high", feedback, False, [], "用户确认应用冲突已处理，需要重新执行应用。")

    if current_phase in {"run", "requirement_alignment"} or project_initialized:
        if contains_any(normalized, IMPACT_KEYWORDS + PRD_REVISION_KEYWORDS + DESIGN_REVISION_KEYWORDS):
            return result("change_impact_requested", "high", feedback, False, [], "深层阶段用户提出需求或设计变更，需影响分析。")

    if current_phase == "run" and phase_status == "waiting_review":
        if contains_any(normalized, START_KEYWORDS):
            return result("start_execution", "high", feedback, False, [], "用户确认开始执行。")
        if contains_any(normalized, AMBIGUOUS_KEYWORDS):
            return choice(feedback, ["start_execution", "change_impact_requested", "show_status"], "运行审核阶段输入存在歧义。")

    if contains_any(normalized, AMBIGUOUS_KEYWORDS):
        return choice(feedback, ["continue_current_flow", "show_status"], "用户输入存在歧义。")

    return result("unknown", "low", feedback, True, ["continue_current_flow", "show_status"], "无法根据当前 session 状态识别用户意图。")


def main():
    args = parse_args()
    try:
        session_id = validate_session_id(args.session_id)
        workspace_root = resolve_workspace_root(args.workspace_root)
        state = load_state_from_path(state_file_path(workspace_root, session_id))
        print(json.dumps(normalize_user_intent(state, args.user_input), ensure_ascii=False, indent=2))
        return 0
    except (SessionStateValidationError, IntentNormalizationError) as exc:
        print(f"归一化用户意图失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
