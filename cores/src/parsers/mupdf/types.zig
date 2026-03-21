pub const DeTextBlock = extern struct {
    bbox_x0: f32,
    bbox_y0: f32,
    bbox_x1: f32,
    bbox_y1: f32,
    block_type: i32,
    line_count: i32,
};

pub const DeTextSpan = extern struct {
    bbox_x0: f32,
    bbox_y0: f32,
    bbox_x1: f32,
    bbox_y1: f32,
    font_name: [128]u8,
    font_size: f32,
    font_flags: u32,
    color: u32,
    block_idx: i32,
    line_idx: i32,
    text_ptr: ?[*]const u8,
    text_len: i32,
};

pub const DeOutlineEntry = extern struct {
    level: i32,
    title: [512]u8,
    page_num: i32,
};

pub const DeImageInfo = extern struct {
    bbox_x0: f32,
    bbox_y0: f32,
    bbox_x1: f32,
    bbox_y1: f32,
    width: i32,
    height: i32,
    image_type: i32,
};
