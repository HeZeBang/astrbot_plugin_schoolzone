"""QZone Feed API 返回值类型定义

基于实际 API 返回的 JSON 结构定义，所有嵌套字段均使用 Optional
以兼容 API 返回数据中可能缺失的字段。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── 通用复用结构 ──────────────────────────────────────────────


@dataclass
class MedalInfo:
    jump_url: str = ""
    level: int = 0
    medal_id: int = 0
    medal_state: int = 0
    medal_type: int = 0
    pic_url: str = ""


@dataclass
class VecCampusInfo:
    e_verfy_status: int = 0
    i_school_idx: int = 0
    str_school_id: str = ""
    str_school_name: str = ""


@dataclass
class Kuoliestate:
    i_days: int = 0
    i_frd_flag: int = 0
    i_frds_cnt: int = 0
    i_last_nuan_time: int = 0
    i_state: int = 0
    str_kuolie_campus_aio_key: str = ""
    vec_campus_info: Optional[VecCampusInfo] = None


@dataclass
class Decoration:
    data: List[str] = field(default_factory=list)
    type: str = ""


@dataclass
class OpenidUsers:
    logo: str = ""
    nickname: str = ""
    openid: str = ""


@dataclass
class StuCombineDiamondInfo:
    is_annual_vip: int = 0
    is_annual_vip_ever: int = 0
    i_show_type: int = 0
    i_vip_level: int = 0


@dataclass
class StuStarInfo:
    is_annual_vip: int = 0
    is_high_star_vip: int = 0
    i_star_level: int = 0
    i_star_status: int = 0


@dataclass
class UserInfo:
    """通用用户信息，用于 comment.user / reply.user / reply.target /
    like.likemans[].user / pic.friendinfo / userinfo.user 等位置。
    """
    actiontype: int = 0
    actionurl: str = ""
    age: int = 0
    authqzone_medal_info: Optional[MedalInfo] = None
    avatar_recom_bar: str = ""
    decoration: Optional[Decoration] = None
    descicon: str = ""
    displayflag: int = 0
    e_user_type_report: int = 0
    # 原始 JSON 中此字段名因位置而异（from / user_from / target_from / friendinfo_from）
    user_from: int = 0
    icon_height: int = 0
    icon_width: int = 0
    i_cur_user_type: int = 0
    is_own: int = 0
    is_owner: int = 0
    is_annual_vip: int = 0
    is_cmt_verify_open: int = 0
    is_famous_white: int = 0
    is_private_mode: int = 0
    is_qzone_user: int = 0
    is_safe_mode_user: int = 0
    is_set_nick_glint: int = 0
    is_sweet_vip: int = 0
    is_video_circle_v_user: int = 0
    i_vip_act_type: int = 0
    kuoliestate: Optional[Kuoliestate] = None
    level: int = 0
    liveshow_medal_info: Optional[MedalInfo] = None
    logo: str = ""
    medal_info: Optional[MedalInfo] = None
    name_plate: int = 0
    nickname: str = ""
    openid_users: Optional[OpenidUsers] = None
    operation_mask: int = 0
    portrait_id: int = 0
    qzonedesc: str = ""
    sex: int = 0
    str_portrait_id: str = ""
    stu_combine_diamond_info: Optional[StuCombineDiamondInfo] = None
    stu_star_info: Optional[StuStarInfo] = None
    tag_infos: List[str] = field(default_factory=list)
    talk_id: str = ""
    timestamp: int = 0
    u_fans_count: int = 0
    u_feeds_count: int = 0
    uid: str = ""
    uin: int = 0
    uinkey: str = ""
    under_nickname_desc: str = ""
    user_tags: List[str] = field(default_factory=list)
    u_visitor_count: int = 0
    vip: int = 0
    viplevel: int = 0
    vip_show_type: int = 0
    viptype: int = 0
    vtime: int = 0


# ── PhotoUrl 图片尺寸 ─────────────────────────────────────────


@dataclass
class PhotoSize:
    """单张图片的某个尺寸（0=缩略 / 1=中图 / 11=大图 / 14=原图 等）"""
    enlarge_rate: int = 0
    focus_x: int = 0
    focus_y: int = 0
    height: int = 0
    md5: str = ""
    size: int = 0
    url: str = ""
    width: int = 0


@dataclass
class PhotoUrl:
    """图片多尺寸地址集合，键为字符串形式的数字"""
    sizes: Dict[str, PhotoSize] = field(default_factory=dict)


# ── UndealInfo ────────────────────────────────────────────────


@dataclass
class UndealInfo:
    active_cnt: int = 0
    gamebar_cnt: int = 0
    gift_cnt: int = 0
    passive_cnt: int = 0
    visitor_cnt: int = 0


# ── Comm（说说元数据） ────────────────────────────────────────


@dataclass
class CommExtendInfo:
    func_type: str = ""
    srcappid: str = ""
    view_count_version_ctr: str = ""


@dataclass
class RightInfo:
    allow_uins: List[str] = field(default_factory=list)
    ugc_right: int = 0


@dataclass
class Comm:
    actiontype: int = 0
    actionurl: str = ""
    adv_stytle: int = 0
    adv_subtype: int = 0
    appid: int = 0
    clientkey: str = ""
    curlikekey: str = ""
    custom_droplist: List[str] = field(default_factory=list)
    editmask: int = 0
    extend_info: Optional[CommExtendInfo] = None
    extend_info_data: Dict[str, Any] = field(default_factory=dict)
    feedsattr: int = 0
    feedsattr2: int = 0
    feedsattr3: int = 0
    feeds_del_time: int = 0
    feedsid: str = ""
    feedskey: str = ""
    feedstype: int = 0
    hot_score: int = 0
    i_click_area: int = 0
    interestkey: str = ""
    is_kuolie: bool = False
    is_stay: bool = False
    lastmodify_time: int = 0
    operatemask: int = 0
    operatemask2: int = 0
    operatemask3: int = 0
    orglikekey: str = ""
    originaltype: int = 0
    paykey: str = ""
    positionmask: int = 0
    positionmask2: int = 0
    pull_qzone: bool = False
    recom_show_type: int = 0
    recomlayout: int = 0
    recomreportid: int = 0
    recomtype: int = 0
    refer: str = ""
    reportfeedsattr: int = 0
    right_info: Optional[RightInfo] = None
    shield: int = 0
    show_mask: int = 0
    space_right: int = 0
    sq_dynamic_feeds_key: str = ""
    st_map_ab_test: Dict[str, Any] = field(default_factory=dict)
    subid: int = 0
    time: int = 0
    uflag: int = 0
    ugckey: str = ""
    ugcrightkey: str = ""
    wup_feeds_type: int = 0


# ── Comment ───────────────────────────────────────────────────


@dataclass
class CommentAudio:
    audiokey: str = ""
    audiotime: int = 0
    errormessge: str = ""
    isplay: int = 0


@dataclass
class CommentExtendInfo:
    is_password_lucky_money_cmt: str = ""
    is_password_lucky_money_cmt_right: str = ""
    public_trans: str = ""


@dataclass
class Reply:
    audio: Optional[CommentAudio] = None
    content: str = ""
    date: int = 0
    displayflag: int = 0
    extend_info: Dict[str, Any] = field(default_factory=dict)
    is_deleted: bool = False
    isliked: int = 0
    likemans: List[str] = field(default_factory=list)
    like_num: int = 0
    refer: str = ""
    replyid: str = ""
    reply_like_key: str = ""
    replypic: List[str] = field(default_factory=list)
    target: Optional[UserInfo] = None
    user: Optional[UserInfo] = None


@dataclass
class CommentElement:
    audio: Optional[CommentAudio] = None
    binary_ext_info: Optional[Dict[str, Any]] = None
    commentid: Optional[str] = None
    comment_likekey: Optional[str] = None
    commentpic: Optional[List[str]] = None
    content: Optional[str] = None
    date: Optional[int] = None
    displayflag: Optional[int] = None
    extend_info: Optional[CommentExtendInfo] = None
    floor: Optional[int] = None
    i_display_reply_num: Optional[int] = None
    is_deleted: Optional[bool] = None
    is_essence: Optional[int] = None
    isliked: Optional[int] = None
    is_private: Optional[int] = None
    is_stick_top: Optional[int] = None
    likemans: Optional[List[str]] = None
    like_num: Optional[int] = None
    picdata: Optional[List[str]] = None
    poke_like_count: Optional[int] = None
    poke_like_emotion: Optional[str] = None
    refer: Optional[str] = None
    replynum: Optional[int] = None
    replys: Optional[List[Reply]] = None
    user: Optional[UserInfo] = None


@dataclass
class MainComment:
    audio: Optional[CommentAudio] = None
    binary_ext_info: Dict[str, Any] = field(default_factory=dict)
    commentid: str = ""
    comment_likekey: str = ""
    commentpic: List[str] = field(default_factory=list)
    content: str = ""
    date: int = 0
    displayflag: int = 0
    extend_info: Dict[str, Any] = field(default_factory=dict)
    floor: int = 0
    i_display_reply_num: int = 0
    is_deleted: bool = False
    is_essence: int = 0
    isliked: int = 0
    is_private: int = 0
    is_stick_top: int = 0
    likemans: List[str] = field(default_factory=list)
    like_num: int = 0
    picdata: List[str] = field(default_factory=list)
    poke_like_count: int = 0
    poke_like_emotion: str = ""
    refer: str = ""
    replynum: int = 0
    replys: List[str] = field(default_factory=list)
    user: Optional[UserInfo] = None


@dataclass
class PlugInInfo:
    action_type: int = 0
    action_url: str = ""
    insert_index: int = 0
    title: str = ""


@dataclass
class VFeedComment:
    actiontype: int = 0
    cntnum: int = 0
    comments: List[CommentElement] = field(default_factory=list)
    displayflag: int = 0
    i_real_count: int = 0
    main_comment: Optional[MainComment] = None
    num: int = 0
    plug_in_info: Optional[PlugInInfo] = None
    txt: str = ""
    unread_cnt: int = 0


# ── Like ──────────────────────────────────────────────────────


@dataclass
class ID:
    cellid: str = ""
    subid: str = ""


@dataclass
class CpolyPraise:
    i_item_id: int = 0
    itype: int = 0
    poke_like_combo: int = 0
    resource_id: int = 0
    str_pic_url: str = ""
    str_text: str = ""


@dataclass
class MetaDataCustom:
    custom_praisetype: int = 0
    i_frame_rate: int = 0
    i_item_id: int = 0
    i_praise_act_id: int = 0
    str_praise_button: str = ""
    str_praise_combo_zip: str = ""
    str_praise_pic: str = ""
    str_praise_zip: str = ""
    subpraisetype: int = 0
    ui_combo_count: int = 0


@dataclass
class CustomPraise:
    i_item_id: int = 0
    meta_data_custom: Optional[MetaDataCustom] = None
    str_praise_pic: str = ""


@dataclass
class Likeman:
    cpoly_praise: Optional[CpolyPraise] = None
    custom_praise: Optional[CustomPraise] = None
    refer: str = ""
    superflag: int = 0
    user: Optional[UserInfo] = None


@dataclass
class Like:
    isliked: int = 0
    likemans: List[Likeman] = field(default_factory=list)
    num: int = 0
    txt: str = ""


# ── Operation ─────────────────────────────────────────────────


@dataclass
class SchemaInfo:
    actiontype: int = 0
    actionurl: str = ""
    appid: str = ""
    appname: str = ""
    downloadurl: str = ""
    loadingpage: bool = False
    master_actionurl: str = ""
    postparams: str = ""
    schemapageurl: str = ""
    usepost: int = 0
    yingyongbao: bool = False


@dataclass
class ArkSharedata:
    ark_content: str = ""
    ark_id: str = ""
    view_id: str = ""


@dataclass
class ShareInfo:
    action_url: str = ""
    ark_sharedata: Optional[ArkSharedata] = None
    photourl: Optional[PhotoUrl] = None
    summary: str = ""
    title: str = ""


@dataclass
class VFeedOperation:
    busi_param: Dict[str, Any] = field(default_factory=dict)
    button_gif_url: str = ""
    bypass_param: Dict[str, Any] = field(default_factory=dict)
    click_stream_report: Dict[str, Any] = field(default_factory=dict)
    custom_btn: List[str] = field(default_factory=list)
    droplist_cookie: Dict[str, Any] = field(default_factory=dict)
    feed_report_cookie: Dict[str, Any] = field(default_factory=dict)
    generic_url: str = ""
    offline_resource_bid: int = 0
    qboss_trace: str = ""
    qq_url: str = ""
    rank_param: Dict[str, Any] = field(default_factory=dict)
    recomm_cookie: Dict[str, Any] = field(default_factory=dict)
    schema_info: Optional[SchemaInfo] = None
    share_info: Optional[ShareInfo] = None
    weixin_url: str = ""


# ── Pic（图片/相册） ──────────────────────────────────────────


@dataclass
class Geo:
    poi_address: str = ""
    poi_id: str = ""
    poi_name: str = ""
    poi_type: int = 0
    poi_x: str = ""
    poi_y: str = ""
    region_name: str = ""


@dataclass
class Cropinfo:
    centerx_scale: int = 0
    centery_scale: int = 0


@dataclass
class LabelInfo:
    client_groupid: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)


@dataclass
class Musicdata:
    coverurl: str = ""
    height: int = 0
    musicid: str = ""
    music_m_id: str = ""
    music_m_url: str = ""
    musictime: int = 0
    music_type: str = ""
    musicurl: str = ""
    title: str = ""
    width: int = 0


@dataclass
class PicHostNick:
    nick: str = ""
    uin: int = 0


@dataclass
class BottomButton:
    actiontype: int = 0
    actionurl: str = ""
    animation_duration: int = 0
    animation_url: str = ""
    appear_time: int = 0
    button_background_img: str = ""
    button_icon: str = ""
    button_img: str = ""
    duration_time: int = 0
    extendinfo: Dict[str, Any] = field(default_factory=dict)
    st_map_ab_test: Dict[str, Any] = field(default_factory=dict)
    text: str = ""


@dataclass
class StKingCard:
    button_title: str = ""
    is_guide: bool = False
    jump_url: str = ""


@dataclass
class Videoremark:
    actiontype: int = 0
    actionurl: str = ""
    icondesc: str = ""
    iconurl: str = ""
    orgwebsite: int = 0
    remark: str = ""


@dataclass
class Weishi:
    cover_url: str = ""
    dc_report: Dict[str, Any] = field(default_factory=dict)
    need_show_related: bool = False
    nick_name: str = ""
    pull_weishi_alg_id: str = ""
    pull_weishi_mask: int = 0
    related_button_text: str = ""
    weishi_clipbrd: str = ""
    weishi_download_url: str = ""
    weishi_feed_id: str = ""
    weishi_file_id: str = ""
    weishi_music_id: str = ""
    weishi_music_name: str = ""
    weishi_music_url: str = ""
    weishi_pull_schema: str = ""
    weishi_schema: str = ""
    weishi_topic_id: str = ""
    weishi_topic_name: str = ""
    weishi_topic_url: str = ""


@dataclass
class Videodata:
    actiontype: int = 0
    actionurl: str = ""
    adv_delay_time: int = 0
    after_layer_jump_url: str = ""
    albumid: str = ""
    anonymity: int = 0
    auto_refresh_second: int = 0
    bottom_button: Optional[BottomButton] = None
    clientkey: str = ""
    coverurl: Dict[str, Any] = field(default_factory=dict)
    cur_video_rate: int = 0
    extendinfo: Dict[str, Any] = field(default_factory=dict)
    filetype: int = 0
    gauss_pic_url: Dict[str, Any] = field(default_factory=dict)
    header_desc: str = ""
    is_share: bool = False
    is_had_set_play_on_wifi: bool = False
    is_on_wifi_play: bool = False
    is_panorama: bool = False
    lloc: str = ""
    need_show_follow_guide_animation: int = 0
    playtype: int = 0
    report_video_feeds_type: int = 0
    sloc: str = ""
    st_king_card: Optional[StKingCard] = None
    toast: str = ""
    vc_covers: List[str] = field(default_factory=list)
    video_click_type: int = 0
    video_desc: str = ""
    video_form: int = 0
    video_max_playtime: int = 0
    video_rate_list: List[str] = field(default_factory=list)
    video_show_type: int = 0
    video_source: int = 0
    video_webview_url: str = ""
    videoid: str = ""
    videoplaycnt: int = 0
    videoremark: Optional[Videoremark] = None
    videostatus: int = 0
    videotime: int = 0
    videotype: int = 0
    videourl: str = ""
    videourls: Dict[str, Any] = field(default_factory=dict)
    weishi: Optional[Weishi] = None


@dataclass
class Picdatum:
    albumid: str = ""
    audio_summary: str = ""
    batchid: int = 0
    binary_ext_info: Dict[str, Any] = field(default_factory=dict)
    busi_param: Dict[str, Any] = field(default_factory=dict)
    clientkey: str = ""
    commentcount: int = 0
    cropinfo: Optional[Cropinfo] = None
    curlikekey: str = ""
    desc: str = ""
    facelist: List[str] = field(default_factory=list)
    facelist_info: List[str] = field(default_factory=list)
    fashion_tag_key: str = ""
    flag: int = 0
    geo: Optional[Geo] = None
    is_auto_play_gif: bool = False
    is_cover_pic: bool = False
    is_independent_ugc: int = 0
    ismylike: bool = False
    label_info: Optional[LabelInfo] = None
    likecount: int = 0
    lloc: str = ""
    lucky_money_desc: str = ""
    map_exif_info: Dict[str, Any] = field(default_factory=dict)
    map_extern: Dict[str, Any] = field(default_factory=dict)
    map_ocr_info: Dict[str, Any] = field(default_factory=dict)
    modifytime: int = 0
    musicdata: Optional[Musicdata] = None
    operation: Optional[VFeedOperation] = None
    opmask: int = 0
    opsynflag: int = 0
    orglikekey: str = ""
    origin_height: int = 0
    origin_phototype: int = 0
    origin_size: int = 0
    origin_width: int = 0
    photo_tag: List[str] = field(default_factory=list)
    photourl: Optional[PhotoUrl] = None
    pic_host_nick: Optional[PicHostNick] = None
    piccategory: int = 0
    picname: str = ""
    poi: Optional[Geo] = None
    quankey: str = ""
    raw: int = 0
    real_lloc: str = ""
    shoottime: int = 0
    shouzhang_extend_map: Dict[str, Any] = field(default_factory=dict)
    sloc: str = ""
    type: int = 0
    upload_uin: int = 0
    u_upload_time: int = 0
    vec_show_drying_tag_info: List[str] = field(default_factory=list)
    videodata: Optional[Videodata] = None
    videoflag: int = 0


@dataclass
class Pic:
    actiontype: int = 0
    actionurl: str = ""
    activealbum: int = 0
    albshowmask: int = 0
    albumanswer: str = ""
    albumid: str = ""
    albumname: str = ""
    albumnum: int = 0
    albumquestion: str = ""
    albumrights: int = 0
    albumtype: int = 0
    allow_access: int = 0
    allow_share: int = 0
    animation_type: int = 0
    anonymity: int = 0
    balbum: bool = False
    busi_param: Dict[str, Any] = field(default_factory=dict)
    desc: str = ""
    extend_actiontype: int = 0
    extend_actionurl: str = ""
    faceman_num: int = 0
    facemans: List[str] = field(default_factory=list)
    friendinfo: Optional[UserInfo] = None
    icon_url: str = ""
    individualalbum: int = 0
    is_contain_video_and_pic: bool = False
    is_share: bool = False
    is_share_owner: bool = False
    is_topped_album: bool = False
    is_video_pic_mix: bool = False
    is_subscribe: bool = False
    lastupdatetime: int = 0
    like_cnt: int = 0
    newestupload: int = 0
    news: str = ""
    picdata: List[Picdatum] = field(default_factory=list)
    qunid: str = ""
    share_new_reason: str = ""
    sharer_count: int = 0
    sharer_wx_info: List[str] = field(default_factory=list)
    sort_type: int = 0
    store_appid: str = ""
    uin: int = 0
    unread_count: int = 0
    uploadnum: int = 0
    view_cnt: int = 0


# ── Summary ───────────────────────────────────────────────────


@dataclass
class Sparkleword:
    extend_info: Dict[str, Any] = field(default_factory=dict)
    span_time: int = 0
    sparkle_color: List[str] = field(default_factory=list)
    sparkle_id: str = ""
    sparkle_json: str = ""


@dataclass
class Summary:
    actiontype: int = 0
    actionurl: str = ""
    hasmore: int = 0
    map_ext: Dict[str, Any] = field(default_factory=dict)
    map_proto_ext: Dict[str, Any] = field(default_factory=dict)
    more_info: str = ""
    sparkleword: Optional[Sparkleword] = None
    summary: str = ""
    summarypic: List[str] = field(default_factory=list)


# ── Userinfo ──────────────────────────────────────────────────


@dataclass
class FeedUserinfo:
    action_desc: str = ""
    actiontype: int = 0
    lucky_money_pics: List[str] = field(default_factory=list)
    user: Optional[UserInfo] = None


# ── Visitor ───────────────────────────────────────────────────


@dataclass
class Visitor:
    mod: int = 0
    myfriend_info: str = ""
    view_count: int = 0
    view_count_byfriends: int = 0
    visitor_count: int = 0
    visitors: List[str] = field(default_factory=list)


# ── VFeed（单条说说） ─────────────────────────────────────────


@dataclass
class VFeed:
    comm: Optional[Comm] = None
    id: Optional[ID] = None
    like: Optional[Like] = None
    operation: Optional[VFeedOperation] = None
    pic: Optional[Pic] = None
    summary: Optional[Summary] = None
    userinfo: Optional[FeedUserinfo] = None
    visitor: Optional[Visitor] = None
    comment: Optional[VFeedComment] = None


# ── 顶层响应 ──────────────────────────────────────────────────


@dataclass
class FeedData:
    attachinfo: str = ""
    hasmore: int = 0
    newcnt: int = 0
    undeal_info: Optional[UndealInfo] = None
    v_feeds: List[VFeed] = field(default_factory=list)


@dataclass
class FeedResult:
    code: int = 0
    data: Optional[FeedData] = None
    message: str = ""
    ret: int = 0


# ── 发布说说响应 ──────────────────────────────────────────────


@dataclass
class PreuploadResult:
    """预上传图片 (preupload=1) 的响应"""
    filelen: int = 0
    filemd5: str = ""


# ── 发布说说响应 ──────────────────────────────────────────────


@dataclass
class PublishUndealInfo:
    active_cnt: int = 0
    gamebar_cnt: int = 0
    gift_cnt: int = 0
    passive_cnt: int = 0
    visitor_cnt: int = 0


@dataclass
class PublishData:
    ret: int = 0
    tid: str = ""
    undeal_info: Optional[PublishUndealInfo] = None


@dataclass
class PublishResult:
    code: int = 0
    data: Optional[PublishData] = None
    default: int = 0
    message: str = ""
    subcode: int = 0
